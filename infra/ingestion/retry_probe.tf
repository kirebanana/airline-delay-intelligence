# Permissionless, finite ASL engine test: synthetic errors, never a service call.
resource "aws_iam_role" "retry_qualification" {
  name = "airline-control-retry-qualification"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow", Action = "sts:AssumeRole", Principal = { Service = "states.amazonaws.com" }
      Condition = {
        StringEquals = { "aws:SourceAccount" = "336805808138" }
        ArnEquals    = { "aws:SourceArn" = "arn:aws:states:us-east-2:336805808138:stateMachine:airline-control-retry-qualification" }
      }
    }]
  })
  lifecycle { prevent_destroy = true }
}

resource "aws_sfn_state_machine" "retry_qualification" {
  name     = "airline-control-retry-qualification"
  role_arn = aws_iam_role.retry_qualification.arn
  type     = "STANDARD"
  publish  = true
  definition = jsonencode({
    StartAt = "Select", TimeoutSeconds = 3
    States = merge({
      Select = {
        Type = "Choice"
        Choices = [for kind in ["transient", "deterministic", "timeout"] : {
          Variable = "$.case", StringEquals = kind, Next = kind
        }]
        Default = "Invalid"
      }
      Invalid  = { Type = "Fail", Error = "InvalidQualificationCase" }
      Complete = { Type = "Succeed" }
      }, { for kind in ["transient", "deterministic", "timeout"] : kind => {
        Type = "Parallel"
        Branches = [{
          StartAt = "Injected_${kind}"
          States = { "Injected_${kind}" = jsondecode(kind == "timeout" ? jsonencode({
            Type = "Wait", Seconds = 10, End = true
            }) : jsonencode({
            Type = "Fail", Error = kind == "transient" ? "S3.SlowDown" : "S3.NoSuchKey"
          })) }
        }]
        Retry = [{ ErrorEquals = ["S3.SlowDown", "S3.ServiceUnavailable", "S3.InternalError"], IntervalSeconds = 1, MaxAttempts = 1, BackoffRate = 1 }]
        Catch = [{ ErrorEquals = ["States.ALL"], ResultPath = "$.error", Next = "Complete" }]
        Next  = "Invalid"
    } })
  })
  lifecycle { prevent_destroy = true }
}
