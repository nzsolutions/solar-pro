import bcrypt
from django.contrib.auth.hashers import BasePasswordHasher, mask_hash


class LaravelBcryptPasswordHasher(BasePasswordHasher):
    """
    Password hasher that validates standard Bcrypt hashes produced by PHP Laravel
    (which use the $2y$ prefix) as well as standard $2b$ and $2a$ hashes.
    """
    algorithm = "laravel_bcrypt"

    def encode(self, password, salt=None):
        # Generate standard bcrypt hash
        if isinstance(password, str):
            password = password.encode('utf-8')
        hashed = bcrypt.hashpw(password, bcrypt.gensalt(rounds=12))
        return hashed.decode('utf-8')

    def verify(self, password, encoded):
        if not encoded:
            return False
        
        # PHP Laravel Bcrypt hashes typically start with $2y$.
        # Python's bcrypt expects $2b$ or $2a$. $2y$ is identical to $2b$.
        normalized_hash = encoded
        if normalized_hash.startswith('$2y$'):
            normalized_hash = '$2b$' + normalized_hash[4:]

        if isinstance(password, str):
            password = password.encode('utf-8')
        if isinstance(normalized_hash, str):
            normalized_hash = normalized_hash.encode('utf-8')

        try:
            return bcrypt.checkpw(password, normalized_hash)
        except Exception:
            return False

    def safe_summary(self, encoded):
        return {
            'algorithm': self.algorithm,
            'salt': mask_hash(encoded, show=2),
            'hash': mask_hash(encoded, show=3),
        }
