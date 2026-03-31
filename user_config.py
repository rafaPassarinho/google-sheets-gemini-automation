import json
import os

from dataclasses import dataclass
from functools import lru_cache
from typing import Optional, Dict

@dataclass(frozen=True)
class UserProfile:
    telegram_user_id: int
    name: str
    spreadsheet_id: str
    placeholder_value: float = 33.36
    timezone: str = "America/Sao_Paulo"
    active: bool = True

def _to_bool(value, default=True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ["true", "1", "yes", "y", "on"]

def _validate_profile(raw: dict) -> UserProfile:
    telegram_user_id = int(raw["telegram_user_id"])
    name = str(raw.get("name", f"user_{telegram_user_id}")).strip()
    spreadsheet_id = str(raw["spreadsheet_id"]).strip()
    if not spreadsheet_id:
        raise ValueError(f"spreadsheet_id vazio para user {telegram_user_id}")
    
    placeholder_value = float(raw.get("placeholder_value", 33.36))
    timezone = str(raw.get("timezone", "America/Sao_Paulo")).strip() or "America/Sao_Paulo"
    active = _to_bool(raw.get("active", True))

    return UserProfile(
        telegram_user_id=telegram_user_id,
        name=name,
        spreadsheet_id=spreadsheet_id,
        placeholder_value=placeholder_value,
        timezone=timezone,
        active=active
    )

@lru_cache(maxsize=1)
def _load_users() -> Dict[int, UserProfile]:
    """
    Carrega usuários a partir de USER_CONFIG_JSON.

    Formato recomendado:
    {
      "users": [
        {
          "telegram_user_id": 123456789,
          "name": "Rafaela",
          "spreadsheet_id": "1AbC...",
          "placeholder_value": 33.36,
          "timezone": "America/Sao_Paulo",
          "active": true
        }
      ]
    }
    """
    cfg = os.getenv("USER_CONFIG_JSON", "").strip()
    users: Dict[int, UserProfile] = {}

    if cfg:
        parsed = json.loads(cfg)
        raw_users = parsed["users"] if isinstance(parsed, dict) else parsed
        if not isinstance(raw_users, list):
            raise ValueError("USER_CONFIG_JSON deve conter uma lista de usuários em 'users' ou ser uma lista direta.")
        
        for raw in raw_users:
            profile = _validate_profile(raw)
            users[profile.telegram_user_id] = profile

        return users
    
    # fallback para 1 usuário (compatibilidade)
    single_id = os.getenv("DEFAULT_TELEGRAM_USER_ID")
    single_sheet = os.getenv("GOOGLE_SHEETS_ID")
    if single_id and single_sheet:
        profile = UserProfile(
            telegram_user_id=int(single_id),
            name=os.getenv("DEFAULT_USER_NAME", "Default"),
            spreadsheet_id=single_sheet,
            placeholder_value=float(os.getenv("DEFAULT_PLACEHOLDER_VALUE", "33.36")),
            timezone=os.getenv("TZ", "America/Sao_Paulo"),
            active=True,
        )
        users[profile.telegram_user_id] = profile

    return users

def reload_user_config():
    """Limpa cache para recarregar configuração de usuários."""
    _load_users.cache_clear()

def get_user(telegram_user_id: int) -> Optional[UserProfile]:
    """Retorna UserProfile para o telegram_user_id ou None se não encontrado."""
    profile = _load_users().get(int(telegram_user_id))
    if profile and profile.active:
        return profile
    return None

def get_spreadsheet_id(telegram_user_id: int) -> Optional[str]:
    """Retorna spreadsheet_id para o telegram_user_id ou None se não encontrado."""
    user = get_user(telegram_user_id)
    return user.spreadsheet_id if user else None
