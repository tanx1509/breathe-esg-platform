"""
Custom JWT serializer that embeds tenant_id and role in the token.
"""
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


class ESGTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Adds tenant_id and role to JWT claims so the frontend
    can display tenant-scoped UI and the middleware can scope queries.
    """

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["tenant_id"] = str(user.tenant_id) if user.tenant_id else None
        token["role"] = user.role
        token["email"] = user.email
        return token
