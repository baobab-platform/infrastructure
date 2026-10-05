resource "aws_efs_file_system_policy" "iam_ledger" {
  count          = var.workload_release == null ? 0 : 1
  file_system_id = aws_efs_file_system.iam_ledger.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "DenyUnencryptedMount", Effect = "Deny", Principal = "*"
        Action    = ["elasticfilesystem:ClientMount", "elasticfilesystem:ClientWrite", "elasticfilesystem:ClientRootAccess"]
        Resource  = aws_efs_file_system.iam_ledger.arn
        Condition = { Bool = { "aws:SecureTransport" = "false" } }
      },
      {
        Sid       = "DenyOtherWriters", Effect = "Deny", Principal = "*"
        Action    = ["elasticfilesystem:ClientMount", "elasticfilesystem:ClientWrite", "elasticfilesystem:ClientRootAccess"]
        Resource  = aws_efs_file_system.iam_ledger.arn
        Condition = { StringNotEquals = { "aws:PrincipalArn" = aws_iam_role.workload["iam"].arn } }
      },
      {
        Sid       = "DenyOtherAccessPoints", Effect = "Deny", Principal = "*"
        Action    = ["elasticfilesystem:ClientMount", "elasticfilesystem:ClientWrite", "elasticfilesystem:ClientRootAccess"]
        Resource  = aws_efs_file_system.iam_ledger.arn
        Condition = { StringNotEquals = { "elasticfilesystem:AccessPointArn" = aws_efs_access_point.iam_ledger.arn } }
      },
      {
        Sid       = "AllowBoundIAMWriter", Effect = "Allow", Principal = { AWS = aws_iam_role.workload["iam"].arn }
        Action    = ["elasticfilesystem:ClientMount", "elasticfilesystem:ClientWrite"]
        Resource  = aws_efs_file_system.iam_ledger.arn
        Condition = { StringEquals = { "elasticfilesystem:AccessPointArn" = aws_efs_access_point.iam_ledger.arn }, Bool = { "aws:SecureTransport" = "true" } }
      }
    ]
  })
}
