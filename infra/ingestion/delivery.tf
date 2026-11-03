# Trusted code delivery only. The GitHub environment restricts deployments to main.
resource "aws_iam_openid_connect_provider" "github" {
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
  lifecycle { prevent_destroy = true }
}

resource "aws_iam_role" "github_release" {
  name                 = "airline-github-release"
  max_session_duration = 3600
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Action    = "sts:AssumeRoleWithWebIdentity"
      Principal = { Federated = aws_iam_openid_connect_provider.github.arn }
      Condition = { StringEquals = {
        "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
        "token.actions.githubusercontent.com:sub" = "repo:kirebanana@173084883/airline-delay-intelligence@1433493412:environment:release"
      } }
    }]
  })
  lifecycle { prevent_destroy = true }
}

resource "aws_iam_role_policy" "github_release" {
  name = "airline-release-only"
  role = aws_iam_role.github_release.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ApplicationStateList", Effect = "Allow", Action = "s3:ListBucket"
        Resource = "arn:aws:s3:::airline-state-336805808138-us-east-2"
        # Terraform lists workspace names; this permits no object reads there.
        Condition = { StringLike = { "s3:prefix" = ["aws/jobs.tfstate", "aws/jobs.tfstate.tflock", "env:/"] } }
      },
      {
        Sid      = "ApplicationState", Effect = "Allow", Action = ["s3:GetObject", "s3:PutObject"]
        Resource = "arn:aws:s3:::airline-state-336805808138-us-east-2/aws/jobs.tfstate"
      },
      {
        Sid      = "ApplicationLock", Effect = "Allow", Action = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
        Resource = "arn:aws:s3:::airline-state-336805808138-us-east-2/aws/jobs.tfstate.tflock"
      },
      {
        Sid       = "RegistryAuthentication", Effect = "Allow", Action = "ecr:GetAuthorizationToken", Resource = "*"
        Condition = { StringEquals = { "aws:RequestedRegion" = "us-east-2" } }
      },
      {
        Sid      = "ProjectImage", Effect = "Allow"
        Action   = ["ecr:BatchCheckLayerAvailability", "ecr:InitiateLayerUpload", "ecr:UploadLayerPart", "ecr:CompleteLayerUpload", "ecr:PutImage", "ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer", "ecr:DescribeImages", "ecr:DescribeImageScanFindings", "ecr:StartImageScan"]
        Resource = "arn:aws:ecr:us-east-2:336805808138:repository/airline-delay-intelligence"
      },
      {
        Sid       = "RegisterRetainedTasks", Effect = "Allow", Action = "ecs:RegisterTaskDefinition"
        Resource  = [for kind in ["acquisition", "warehouse", "publisher"] : "arn:aws:ecs:us-east-2:336805808138:task-definition/airline-stage-${kind}:*"]
        Condition = { StringEquals = { "aws:RequestedRegion" = "us-east-2" } }
      },
      {
        # AWS does not support resource-level authorization for this read API.
        Sid       = "DescribeTaskDefinitions", Effect = "Allow", Action = "ecs:DescribeTaskDefinition", Resource = "*"
        Condition = { StringEquals = { "aws:RequestedRegion" = "us-east-2" } }
      },
      {
        Sid      = "ReadRetainedTasks", Effect = "Allow", Action = ["ecs:ListTagsForResource", "ecs:TagResource"]
        Resource = [for kind in ["acquisition", "warehouse", "publisher"] : "arn:aws:ecs:us-east-2:336805808138:task-definition/airline-stage-${kind}:*"]
      },
      {
        Sid      = "ObserveTaskAdmission", Effect = "Allow", Action = "ecs:ListTasks"
        Resource = "arn:aws:ecs:us-east-2:336805808138:cluster/airline-jobs"
      },
      {
        Sid      = "ObserveRefreshAdmission", Effect = "Allow", Action = "states:ListExecutions"
        Resource = "arn:aws:states:us-east-2:336805808138:stateMachine:airline-isolated-refresh"
      },
      {
        # Definition validation does not execute a state or accept a resource ARN.
        Sid       = "ValidateWorkflow", Effect = "Allow", Action = "states:ValidateStateMachineDefinition", Resource = "*"
        Condition = { StringEquals = { "aws:RequestedRegion" = "us-east-2" } }
      },
      {
        Sid      = "WorkflowRevision", Effect = "Allow"
        Action   = ["states:DescribeStateMachine", "states:ListStateMachineVersions", "states:ListTagsForResource", "states:UpdateStateMachine", "states:PublishStateMachineVersion"]
        Resource = "arn:aws:states:us-east-2:336805808138:stateMachine:airline-isolated-refresh"
      },
      {
        Sid       = "PassExactTaskRoles", Effect = "Allow", Action = "iam:PassRole"
        Resource  = [for name in ["acquisition", "warehouse", "publisher", "execution"] : "arn:aws:iam::336805808138:role/airline-job-${name}"]
        Condition = { StringEquals = { "iam:PassedToService" = "ecs-tasks.amazonaws.com" } }
      },
      {
        Sid       = "PassExactWorkflowRole", Effect = "Allow", Action = "iam:PassRole"
        Resource  = "arn:aws:iam::336805808138:role/airline-refresh-workflow"
        Condition = { StringEquals = { "iam:PassedToService" = "states.amazonaws.com" } }
      },
      {
        Sid      = "NeverStartData", Effect = "Deny", Action = ["ecs:RunTask", "ecs:StartTask", "ecs:CreateService", "ecs:UpdateService", "states:StartExecution", "states:StartSyncExecution", "events:PutRule", "scheduler:CreateSchedule", "secretsmanager:GetSecretValue", "ssm:GetParameter", "ssm:GetParameters", "iam:Create*", "iam:Update*", "iam:Put*", "iam:Attach*", "iam:Delete*", "sts:AssumeRole"]
        Resource = "*"
      }
    ]
  })
}
