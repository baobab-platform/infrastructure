// Runtime helper is infrastructure-owned. It never decides application identity.
package main

import (
	"context"
	"crypto/tls"
	"crypto/x509"
	"encoding/base64"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"net/http"
	"net/http/httputil"
	"net/url"
	"os"
	"os/signal"
	"path/filepath"
	"regexp"
	"strings"
	"syscall"
	"time"

	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/config"
	"github.com/aws/aws-sdk-go-v2/service/secretsmanager"
)

type secretFile struct {
	Path   string `json:"path"`
	Base64 string `json:"base64"`
}
type bundle struct {
	Files []secretFile `json:"files"`
}

func uniqueJSON(decoder *json.Decoder) error {
	token, err := decoder.Token()
	if err != nil {
		return err
	}
	delimiter, ok := token.(json.Delim)
	if !ok {
		return nil
	}
	if delimiter == '{' {
		seen := map[string]bool{}
		for decoder.More() {
			token, err := decoder.Token()
			if err != nil {
				return err
			}
			name, ok := token.(string)
			if !ok || seen[name] {
				return errors.New("duplicate JSON field")
			}
			seen[name] = true
			if err := uniqueJSON(decoder); err != nil {
				return err
			}
		}
	} else if delimiter == '[' {
		for decoder.More() {
			if err := uniqueJSON(decoder); err != nil {
				return err
			}
		}
	} else {
		return errors.New("invalid JSON")
	}
	_, err = decoder.Token()
	return err
}

var namePattern = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$`)

func decodeBundle(raw string, expected []string) (map[string][]byte, error) {
	if len(raw) > 65536 || len(expected) == 0 || len(expected) > 64 {
		return nil, errors.New("invalid bundle")
	}
	check := json.NewDecoder(strings.NewReader(raw))
	if uniqueJSON(check) != nil {
		return nil, errors.New("invalid JSON")
	}
	if _, err := check.Token(); err != io.EOF {
		return nil, errors.New("trailing JSON")
	}
	var b bundle
	decoder := json.NewDecoder(strings.NewReader(raw))
	decoder.DisallowUnknownFields()
	if decoder.Decode(&b) != nil || decoder.Decode(new(any)) != io.EOF || len(b.Files) != len(expected) {
		return nil, errors.New("invalid bundle")
	}
	allowed := map[string]bool{}
	for _, name := range expected {
		if !namePattern.MatchString(name) || name == "runtime-helper" || allowed[name] {
			return nil, errors.New("invalid names")
		}
		allowed[name] = true
	}
	result := map[string][]byte{}
	for _, file := range b.Files {
		if !allowed[file.Path] || result[file.Path] != nil {
			return nil, errors.New("invalid file")
		}
		data, err := base64.StdEncoding.Strict().DecodeString(file.Base64)
		if err != nil || len(data) == 0 || len(data) > 65536 {
			return nil, errors.New("invalid content")
		}
		result[file.Path] = data
	}
	return result, nil
}
func materialize(ctx context.Context, dir string, uid int) error {
	if uid < 1 || uid > 65534 || dir != "/run/baobab" {
		return errors.New("invalid destination")
	}
	var names []string
	if json.Unmarshal([]byte(os.Getenv("BUNDLE_FILES")), &names) != nil {
		return errors.New("invalid manifest")
	}
	arn, version := os.Getenv("BUNDLE_SECRET_ARN"), os.Getenv("BUNDLE_VERSION_ID")
	if !strings.HasPrefix(arn, "arn:aws:secretsmanager:af-south-1:") || len(version) < 32 || len(version) > 64 {
		return errors.New("invalid secret reference")
	}
	cfg, err := config.LoadDefaultConfig(ctx, config.WithRegion("af-south-1"))
	if err != nil {
		return err
	}
	response, err := secretsmanager.NewFromConfig(cfg).GetSecretValue(ctx, &secretsmanager.GetSecretValueInput{SecretId: aws.String(arn), VersionId: aws.String(version)})
	if err != nil || response.SecretString == nil || aws.ToString(response.VersionId) != version {
		return errors.New("secret read denied")
	}
	files, err := decodeBundle(*response.SecretString, names)
	if err != nil {
		return err
	}
	executable, err := os.Executable()
	if err != nil {
		return err
	}
	binary, err := os.ReadFile(executable)
	if err != nil {
		return err
	}
	files["runtime-helper"] = binary
	return writeFiles(dir, uid, files)
}
func writeFiles(dir string, uid int, files map[string][]byte) error {
	info, err := os.Lstat(dir)
	if err != nil || !info.IsDir() || info.Mode()&os.ModeSymlink != 0 {
		return errors.New("invalid mount")
	}
	stage, err := os.MkdirTemp(dir, ".pending-")
	if err != nil {
		return err
	}
	defer os.RemoveAll(stage)
	for name, data := range files {
		if !namePattern.MatchString(name) {
			return errors.New("invalid filename")
		}
		mode := os.FileMode(0600)
		if name == "runtime-helper" {
			mode = 0500
		}
		f, err := os.OpenFile(filepath.Join(stage, name), os.O_WRONLY|os.O_CREATE|os.O_EXCL|syscall.O_NOFOLLOW, mode)
		if err != nil {
			return err
		}
		_, err = f.Write(data)
		if err == nil {
			err = f.Chown(uid, uid)
		}
		if err == nil {
			err = f.Sync()
		}
		closeErr := f.Close()
		if err != nil {
			return err
		}
		if closeErr != nil {
			return closeErr
		}
	}
	// Task ordering with SUCCESS keeps applications stopped until every file exists.
	for name := range files {
		destination := filepath.Join(dir, name)
		if _, err := os.Lstat(destination); !os.IsNotExist(err) {
			return errors.New("destination exists")
		}
		if err := os.Rename(filepath.Join(stage, name), destination); err != nil {
			return err
		}
	}
	if err := os.Chown(dir, uid, uid); err != nil {
		return err
	}
	return os.Chmod(dir, 0700)
}
func protected(path string) ([]byte, error) {
	f, err := os.OpenFile(path, os.O_RDONLY|syscall.O_NOFOLLOW, 0)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	info, err := f.Stat()
	if err != nil {
		return nil, err
	}
	stat, ok := info.Sys().(*syscall.Stat_t)
	if !ok || !info.Mode().IsRegular() || info.Mode().Perm() != 0600 || int(stat.Uid) != os.Getuid() || stat.Nlink != 1 || info.Size() > 65536 {
		return nil, errors.New("unprotected file")
	}
	return io.ReadAll(io.LimitReader(f, 65537))
}
func tlsFiles(ca, cert, key string) (*tls.Config, error) {
	raw, err := protected(ca)
	if err != nil {
		return nil, err
	}
	roots := x509.NewCertPool()
	if !roots.AppendCertsFromPEM(raw) {
		return nil, errors.New("invalid roots")
	}
	certData, err := protected(cert)
	if err != nil {
		return nil, err
	}
	keyData, err := protected(key)
	if err != nil {
		return nil, err
	}
	pair, err := tls.X509KeyPair(certData, keyData)
	if err != nil {
		return nil, err
	}
	return &tls.Config{MinVersion: tls.VersionTLS12, RootCAs: roots, ClientCAs: roots, Certificates: []tls.Certificate{pair}}, nil
}
func run(ctx context.Context, mode, dir string, uid int, address, upstream, probe, serverName, ca, cert, key string) error {
	if mode == "materialize" {
		return materialize(ctx, dir, uid)
	}
	tlsConfig, err := tlsFiles(ca, cert, key)
	if err != nil {
		return err
	}
	if mode == "probe" {
		target, err := url.Parse(probe)
		if err != nil || target.Scheme != "https" || target.Hostname() != "127.0.0.1" || target.User != nil || target.RawQuery != "" || target.Fragment != "" || serverName == "" {
			return errors.New("invalid probe")
		}
		tlsConfig.ServerName = serverName
		client := &http.Client{Timeout: 5 * time.Second, Transport: &http.Transport{TLSClientConfig: tlsConfig}, CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }}
		req, err := http.NewRequestWithContext(ctx, "GET", probe, nil)
		if err != nil {
			return err
		}
		resp, err := client.Do(req)
		if err != nil {
			return err
		}
		defer resp.Body.Close()
		if resp.StatusCode < 200 || resp.StatusCode > 299 {
			return errors.New("not ready")
		}
		return nil
	}
	if mode != "proxy" {
		return errors.New("invalid mode")
	}
	target, err := url.Parse(upstream)
	if err != nil || target.Scheme != "http" || target.Hostname() != "127.0.0.1" || target.User != nil || target.Path != "" || target.RawQuery != "" || target.Fragment != "" {
		return errors.New("invalid upstream")
	}
	proxy := httputil.NewSingleHostReverseProxy(target)
	proxy.Transport = &http.Transport{ResponseHeaderTimeout: 10 * time.Second, IdleConnTimeout: 30 * time.Second}
	proxy.ErrorHandler = func(w http.ResponseWriter, r *http.Request, _ error) {
		http.Error(w, "private upstream unavailable", http.StatusBadGateway)
	}
	tlsConfig.ClientAuth = tls.RequireAndVerifyClientCert
	handler := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/_transport/health" {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		if strings.EqualFold(r.Header.Get("Upgrade"), "websocket") {
			http.Error(w, "upgrade denied", 400)
			return
		}
		requestCtx, cancel := context.WithTimeout(r.Context(), 25*time.Second)
		defer cancel()
		proxy.ServeHTTP(w, r.WithContext(requestCtx))
	})
	server := &http.Server{Addr: address, Handler: handler, TLSConfig: tlsConfig, ReadHeaderTimeout: 5 * time.Second, ReadTimeout: 30 * time.Second, WriteTimeout: 30 * time.Second, IdleTimeout: 60 * time.Second, MaxHeaderBytes: 16384}
	result := make(chan error, 1)
	go func() { result <- server.ListenAndServeTLS("", "") }()
	select {
	case err := <-result:
		if errors.Is(err, http.ErrServerClosed) {
			return nil
		}
		return err
	case <-ctx.Done():
		shutdown, cancel := context.WithTimeout(context.Background(), 30*time.Second)
		defer cancel()
		return server.Shutdown(shutdown)
	}
}
func main() {
	mode := flag.String("mode", "", "materialize, proxy or probe")
	dir := flag.String("directory", "/run/baobab", "protected volume")
	uid := flag.Int("uid", 65532, "application uid")
	address := flag.String("listen", ":8443", "private TLS address")
	upstream := flag.String("upstream", "http://127.0.0.1:8080", "loopback application")
	probe := flag.String("url", "", "loopback HTTPS readiness URL")
	name := flag.String("server-name", "", "verified TLS name")
	ca := flag.String("ca", "/run/baobab/ca.pem", "trust roots")
	cert := flag.String("cert", "/run/baobab/service.pem", "certificate")
	key := flag.String("key", "/run/baobab/service.key", "key")
	flag.Parse()
	ctx, cancel := signal.NotifyContext(context.Background(), syscall.SIGTERM, syscall.SIGINT)
	defer cancel()
	if err := run(ctx, *mode, *dir, *uid, *address, *upstream, *probe, *name, *ca, *cert, *key); err != nil {
		fmt.Fprintln(os.Stderr, "runtime helper operation denied")
		os.Exit(1)
	}
}
