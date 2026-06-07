package ci.security

# Deny if containers run as root user
deny[msg] {
  input.kind == "Pod"
  some i
  container := input.spec.containers[i]
  not container.securityContext.runAsNonRoot
  msg := sprintf("Container '%s' must not run as root user", [container.name])
}

# Deny if containers are privileged
deny[msg] {
  input.kind == "Pod"
  some i
  container := input.spec.containers[i]
  container.securityContext.privileged == true
  msg := sprintf("Container '%s' must not be privileged", [container.name])
}

# Deny if resource limits are not set
deny[msg] {
  input.kind == "Pod"
  some i
  container := input.spec.containers[i]
  not container.resources.limits
  msg := sprintf("Container '%s' must set resource limits", [container.name])
}

# Deny if image tag is 'latest'
deny[msg] {
  input.kind == "Pod"
  some i
  container := input.spec.containers[i]
  endswith(container.image, ":latest")
  msg := sprintf("Container '%s' must not use 'latest' tag for image", [container.name])
}