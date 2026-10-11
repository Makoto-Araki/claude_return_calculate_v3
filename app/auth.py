"""APIキー認証と、ユーザー設定ファイルの読み込みを提供する。

認証はヘッダー ``X-API-Key`` で行い、キーからユーザーを特定する。
キーはログ・レスポンス・エラーメッセージのいずれにも出さない。
"""

import hmac
import os
import tomllib
from pathlib import Path
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from fastapi.security import APIKeyHeader

DEFAULT_USERS_PATH = Path("config/users.toml")
USERS_PATH_ENV = "USERS_CONFIG_PATH"

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


class UsersConfigError(ValueError):
    """ユーザー設定ファイルの異常（欠落・形式不正・重複など）を表す。

    メッセージにはどの項目が悪いかだけを書き、キーの値は含めない。
    """


def get_users_path() -> Path:
    """ユーザー設定ファイルの場所を返す。

    Returns
    -------
    Path
        環境変数 ``USERS_CONFIG_PATH`` があればその値、なければ
        ``config/users.toml``（相対パスのまま）。
    """
    value = os.environ.get(USERS_PATH_ENV)
    return Path(value) if value else DEFAULT_USERS_PATH


def load_users(path: Path) -> dict[str, str]:
    """ユーザー設定ファイル（TOML）を読み、検証して返す。

    ``[[users]]`` は 1 件以上で、``name`` と ``api_key`` は空でない文字列、
    どちらもユーザー間で重複してはならない。

    Parameters
    ----------
    path : Path
        設定ファイルのパス。

    Returns
    -------
    dict[str, str]
        API キーをユーザー名に対応づけた辞書。

    Raises
    ------
    UsersConfigError
        ファイルがない、UTF-8 として読めない、TOML として不正、ユーザーが 0 件、
        項目が欠落・空・文字列でない、または ``name`` / ``api_key`` が重複している場合。
    """
    try:
        with path.open("rb") as file:
            data = tomllib.load(file)
    except FileNotFoundError:
        raise UsersConfigError("users config file not found") from None
    except UnicodeDecodeError:
        raise UsersConfigError("users config is not readable as UTF-8") from None
    except tomllib.TOMLDecodeError:
        raise UsersConfigError("users config is not valid TOML") from None
    except OSError:
        raise UsersConfigError("users config file cannot be read") from None

    users = data.get("users")
    if not isinstance(users, list) or not users:
        raise UsersConfigError("users config must have at least one [[users]]")

    keys_to_names: dict[str, str] = {}
    names: set[str] = set()
    for index, user in enumerate(users):
        if not isinstance(user, dict):
            raise UsersConfigError(f"users[{index}] must be a table")
        name = user.get("name")
        api_key = user.get("api_key")
        if not isinstance(name, str) or not name:
            raise UsersConfigError(f"users[{index}].name must be a non-empty string")
        if not isinstance(api_key, str) or not api_key:
            raise UsersConfigError(f"users[{index}].api_key must be a non-empty string")
        if name in names:
            raise UsersConfigError(f"users[{index}].name is duplicated")
        if api_key in keys_to_names:
            raise UsersConfigError(f"users[{index}].api_key is duplicated")
        names.add(name)
        keys_to_names[api_key] = name
    return keys_to_names


def get_users(request: Request) -> dict[str, str]:
    """認証に使うユーザー一覧（API キーからユーザー名への対応）を返す。

    起動時に読み込んだ設定を返す。テストでは依存関係の上書きで差し替える。

    Parameters
    ----------
    request : Request
        現在のリクエスト。

    Returns
    -------
    dict[str, str]
        API キーをユーザー名に対応づけた辞書。
    """
    users: dict[str, str] = request.app.state.users
    return users


def authenticate(
    api_key: Annotated[str | None, Depends(api_key_header)],
    users: Annotated[dict[str, str], Depends(get_users)],
) -> str:
    """``X-API-Key`` を検証し、対応するユーザー名を返す。

    ヘッダーなし、不一致、空、前後に空白あり、ASCII 以外を含むキーは、
    区別せずすべて同じ 401 とする。ヘッダー値の空白は取り除かない。

    Parameters
    ----------
    api_key : str or None
        ``X-API-Key`` ヘッダーの値。ヘッダーがなければ None。
    users : dict[str, str]
        API キーをユーザー名に対応づけた辞書。

    Returns
    -------
    str
        認証されたユーザー名。

    Raises
    ------
    HTTPException
        認証に失敗した場合（401、本文は ``Invalid API key``）。
    """
    matched: str | None = None
    if api_key:
        candidate = api_key.encode("utf-8", errors="surrogateescape")
        # 一致しても途中で止めず、全ユーザーのキーと比べる。
        for key, name in users.items():
            if hmac.compare_digest(candidate, key.encode("utf-8")):
                matched = name
    if matched is None:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return matched
