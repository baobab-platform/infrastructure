mock_provider "aws" {}

run "foundation_only" {
  command = plan
  assert {
    condition     = length(aws_ecs_service.workload) == 0 && length(aws_db_instance.workloads) == 0 && length(aws_lb.browser) == 0
    error_message = "Foundation-only operation must not create workloads, databases or a public load balancer."
  }
  assert {
    condition     = aws_efs_access_point.iam_ledger.posix_user[0].uid == 65532 && aws_efs_access_point.iam_ledger.root_directory[0].creation_info[0].permissions == "0700"
    error_message = "EFS must match IAM's nonroot image user and remain private."
  }
}
run "prepared_release" {
  command = plan
  variables {
    workload_release = jsondecode(file("tests/release.fixture.json"))
  }
  assert {
    condition     = alltrue([for service in aws_ecs_service.workload : service.desired_count == 0 && service.network_configuration[0].assign_public_ip == false])
    error_message = "Prepared releases must remain stopped and private before activation."
  }
  assert {
    condition     = aws_ecs_service.workload["iam"].deployment_maximum_percent == 100 && aws_ecs_service.workload["iam"].deployment_minimum_healthy_percent == 0
    error_message = "IAM rolling replacement must never request a concurrent second ledger writer."
  }
  assert {
    condition     = alltrue([for db in aws_db_instance.workloads : db.multi_az && !db.publicly_accessible && db.storage_encrypted && db.manage_master_user_password && db.backup_retention_period >= 7])
    error_message = "Databases require private encrypted Multi-AZ storage, managed bootstrap credentials and backups."
  }
  assert {
    condition     = aws_lb_target_group.apisix[0].port == 9443 && aws_lb_target_group.apisix[0].protocol == "HTTPS" && aws_lb_listener.browser[0].default_action[0].type == "fixed-response"
    error_message = "Only APISIX may receive public listener traffic and unmatched routes must deny."
  }
  assert {
    condition     = !contains(keys(local.workload_links), "apisix_iam")
    error_message = "The private federation authority has no gateway edge ingress."
  }
}
run "reject_mutable_image" {
  command = plan
  variables {
    workload_release = merge(jsondecode(file("tests/release.fixture.json")), { helper_image = "registry.example.test/helper:latest" })
  }
  expect_failures = [var.workload_release]
}
run "reject_master_realm" {
  command = plan
  variables {
    workload_release = merge(jsondecode(file("tests/release.fixture.json")), { browser_realms = ["master"] })
  }
  expect_failures = [var.workload_release]
}
run "reject_unprepared_activation" {
  command = plan
  variables {
    workload_release   = jsondecode(file("tests/release.fixture.json"))
    activate_workloads = true
  }
  expect_failures = [aws_ecs_service.workload]
}


run "prepared_shared_iam_storage" {
  command = plan
  override_resource {
    target          = aws_security_group.iam
    values          = { id = "sg-11111111111111111" }
    override_during = plan
  }
  override_resource {
    target          = aws_security_group.database["iam"]
    values          = { id = "sg-22222222222222222" }
    override_during = plan
  }
  variables {
    workload_release    = jsondecode(file("tests/release.fixture.json"))
    iam_shared_postgres = true
  }
  assert {
    condition     = length(aws_db_instance.workloads) == 3 && aws_db_instance.workloads["iam"].db_name == "federation" && aws_db_instance.workloads["iam"].multi_az && !aws_db_instance.workloads["iam"].publicly_accessible
    error_message = "IAM shared state requires its own private encrypted Multi-AZ database."
  }
  assert {
    condition     = aws_vpc_security_group_ingress_rule.database["iam"].referenced_security_group_id == aws_security_group.iam.id && aws_vpc_security_group_egress_rule.database["iam"].referenced_security_group_id == aws_security_group.database["iam"].id
    error_message = "Only the IAM task security group can reach IAM PostgreSQL."
  }
}
