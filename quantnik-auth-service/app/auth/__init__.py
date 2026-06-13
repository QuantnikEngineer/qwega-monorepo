"""
Authentication Layer
====================
Three-layer authentication model:
  Layer 1: PasswordAuthenticator — credential validation (argon2-cffi)
  Layer 2: UserLinker — external identity → internal User
  Layer 3: SessionIssuer — JWT pair creation + session management
"""

