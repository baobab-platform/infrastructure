package main

import (
	"context"
	"crypto/rand"
	"crypto/rsa"
	"crypto/x509"
	"crypto/x509/pkix"
	"encoding/pem"
	"math/big"
	"net"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestBundleRejectsTraversalUnexpectedDuplicateAndInvalidMaterial(t *testing.T) {
	for _, raw := range []string{
		`{"files":[{"path":"../key","base64":"eA=="}]}`,
		`{"files":[{"path":"unapproved","base64":"eA=="}]}`,
		`{"files":[{"path":"key","base64":""}]}`,
		`{"files":[{"path":"key","base64":"eA==","extra":"x"}]}`,
		`{"files":[{"path":"key","base64":"eA=="},{"path":"key","base64":"eA=="}]}`,
		`{"files":[{"path":"key","base64":"eA=="}]} {}`,
		`{"files":[],"files":[{"path":"key","base64":"eA=="}]}`,
		`{"files":[{"path":"key","path":"key","base64":"eA=="}]}`,
	} {
		if _, err := decodeBundle(raw, []string{"key"}); err == nil {
			t.Fatal("invalid bundle accepted")
		}
	}
	files, err := decodeBundle(`{"files":[{"path":"key","base64":"eA=="}]}`, []string{"key"})
	if err != nil || string(files["key"]) != "x" {
		t.Fatal(err)
	}
	if _, err := decodeBundle(`{"files":[{"path":"runtime-helper","base64":"eA=="}]}`, []string{"runtime-helper"}); err == nil {
		t.Fatal("executable substitution accepted")
	}
}
func TestFilesPrivateOwnedAndNoDestinationOverwrite(t *testing.T) {
	dir := t.TempDir()
	if err := writeFiles(dir, os.Getuid(), map[string][]byte{"key": []byte("protected")}); err != nil {
		t.Fatal(err)
	}
	content, err := protected(filepath.Join(dir, "key"))
	if err != nil || string(content) != "protected" {
		t.Fatal(err)
	}
	if err := writeFiles(dir, os.Getuid(), map[string][]byte{"key": []byte("replacement")}); err == nil {
		t.Fatal("existing secret replaced")
	}
	if err := os.Chmod(filepath.Join(dir, "key"), 0644); err != nil {
		t.Fatal(err)
	}
	if _, err := protected(filepath.Join(dir, "key")); err == nil {
		t.Fatal("publicly readable secret accepted")
	}
	if err := os.Chmod(filepath.Join(dir, "key"), 0600); err != nil {
		t.Fatal(err)
	}
	link := filepath.Join(dir, "link")
	if err := os.Symlink(filepath.Join(dir, "key"), link); err != nil {
		t.Fatal(err)
	}
	if _, err := protected(link); err == nil {
		t.Fatal("symlink accepted")
	}
	if err := os.Link(filepath.Join(dir, "key"), filepath.Join(dir, "hardlink")); err != nil {
		t.Fatal(err)
	}
	if _, err := protected(filepath.Join(dir, "key")); err == nil {
		t.Fatal("multiply linked private file accepted")
	}
}
func tlsFixture(t *testing.T) (string, string, string) {
	t.Helper()
	key, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		t.Fatal(err)
	}
	template := &x509.Certificate{SerialNumber: big.NewInt(1), Subject: pkix.Name{CommonName: "private.test"}, DNSNames: []string{"private.test"}, IPAddresses: []net.IP{net.ParseIP("127.0.0.1")}, NotBefore: time.Now().Add(-time.Minute), NotAfter: time.Now().Add(time.Hour), IsCA: true, BasicConstraintsValid: true, KeyUsage: x509.KeyUsageCertSign | x509.KeyUsageDigitalSignature, ExtKeyUsage: []x509.ExtKeyUsage{x509.ExtKeyUsageServerAuth, x509.ExtKeyUsageClientAuth}}
	der, err := x509.CreateCertificate(rand.Reader, template, template, &key.PublicKey, key)
	if err != nil {
		t.Fatal(err)
	}
	dir := t.TempDir()
	cert := filepath.Join(dir, "cert")
	private := filepath.Join(dir, "key")
	root := filepath.Join(dir, "root")
	certBytes := pem.EncodeToMemory(&pem.Block{Type: "CERTIFICATE", Bytes: der})
	for path, data := range map[string][]byte{cert: certBytes, root: certBytes, private: pem.EncodeToMemory(&pem.Block{Type: "RSA PRIVATE KEY", Bytes: x509.MarshalPKCS1PrivateKey(key)})} {
		if err := os.WriteFile(path, data, 0600); err != nil {
			t.Fatal(err)
		}
	}
	return root, cert, private
}
func TestProbeVerifiesTLSIdentityAndDeniesRedirect(t *testing.T) {
	ca, cert, key := tlsFixture(t)
	tlsConfig, err := tlsFiles(ca, cert, key)
	if err != nil {
		t.Fatal(err)
	}
	status := http.StatusNoContent
	server := httptest.NewUnstartedServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Location", "https://other.test")
		w.WriteHeader(status)
	}))
	server.TLS = tlsConfig
	server.StartTLS()
	defer server.Close()
	probe := func(name string) error {
		return run(context.Background(), "probe", "", 1, "", "", server.URL, ""+name, ca, cert, key)
	}
	if err := probe("private.test"); err != nil {
		t.Fatal(err)
	}
	if probe("wrong.test") == nil {
		t.Fatal("wrong certificate name accepted")
	}
	status = http.StatusFound
	if probe("private.test") == nil {
		t.Fatal("redirect counted as readiness")
	}
}
