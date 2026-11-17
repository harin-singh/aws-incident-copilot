# EKS access entries give the investigation and remediation roles Kubernetes
# API access. AmazonEKSViewPolicy / AmazonEKSEditPolicy are the least-privilege
# AWS-managed access policies that replace ad-hoc aws-auth ConfigMap edits.

resource "aws_eks_access_entry" "investigation" {
  for_each = toset(var.eks_cluster_names)

  cluster_name  = each.value
  principal_arn = aws_iam_role.incident_copilot.arn
  type          = "STANDARD"
}

resource "aws_eks_access_policy_association" "investigation_view" {
  for_each = toset(var.eks_cluster_names)

  cluster_name  = each.value
  principal_arn = aws_iam_role.incident_copilot.arn
  policy_arn    = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSViewPolicy"

  access_scope {
    type = "cluster"
  }

  depends_on = [aws_eks_access_entry.investigation]
}

resource "aws_eks_access_entry" "remediation" {
  for_each = toset(var.eks_cluster_names)

  cluster_name  = each.value
  principal_arn = aws_iam_role.remediation.arn
  type          = "STANDARD"
}

resource "aws_eks_access_policy_association" "remediation_edit" {
  for_each = toset(var.eks_cluster_names)

  cluster_name  = each.value
  principal_arn = aws_iam_role.remediation.arn
  policy_arn    = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSEditPolicy"

  access_scope {
    type       = length(var.eks_remediation_namespaces) > 0 ? "namespace" : "cluster"
    namespaces = length(var.eks_remediation_namespaces) > 0 ? var.eks_remediation_namespaces : null
  }

  depends_on = [aws_eks_access_entry.remediation]
}
