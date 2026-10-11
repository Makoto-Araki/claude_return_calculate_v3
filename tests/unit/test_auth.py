"""認証（設定ファイルの読み込み、X-API-Key の検証、401）の仕様を検証する。"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.auth import UsersConfigError, get_users_path, load_users
from app.main import app

ALICE_KEY = "dummy-key-for-alice"
BOB_KEY = "dummy-key-for-bob"
VALID_TOML = f"""
[[users]]
name = "alice"
api_key = "{ALICE_KEY}"

[[users]]
name = "bob"
api_key = "{BOB_KEY}"
"""
UNAUTHORIZED_BODY = {"detail": "Invalid API key"}


def write_config(tmp_path: Path, text: str) -> Path:
    """設定ファイルを一時ディレクトリに書き、そのパスを返す。"""
    path = tmp_path / "users.toml"
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def anon_client() -> TestClient:
    """キーを付けないテスト用の HTTP クライアントを返す。"""
    return TestClient(app)


# --- 設定の読み込み ---


def test_load_users_returns_key_to_name_mapping(tmp_path: Path) -> None:
    """複数ユーザーの設定から {api_key: name} が返ること。"""
    path = write_config(tmp_path, VALID_TOML)
    assert load_users(path) == {ALICE_KEY: "alice", BOB_KEY: "bob"}


def test_load_users_missing_file_raises(tmp_path: Path) -> None:
    """設定ファイルが存在しないと UsersConfigError になること。"""
    with pytest.raises(UsersConfigError):
        load_users(tmp_path / "nothing.toml")


def test_load_users_invalid_toml_raises(tmp_path: Path) -> None:
    """TOML として不正な内容だと UsersConfigError になること。"""
    path = write_config(tmp_path, "[[users\nname = ")
    with pytest.raises(UsersConfigError):
        load_users(path)


def test_load_users_without_users_table_raises(tmp_path: Path) -> None:
    """[[users]] がない設定だと UsersConfigError になること。"""
    path = write_config(tmp_path, 'title = "x"\n')
    with pytest.raises(UsersConfigError):
        load_users(path)


def test_load_users_empty_users_raises(tmp_path: Path) -> None:
    """ユーザー一覧が 0 件の設定だと UsersConfigError になること。"""
    path = write_config(tmp_path, "users = []\n")
    with pytest.raises(UsersConfigError):
        load_users(path)


def test_load_users_missing_name_raises(tmp_path: Path) -> None:
    """設定の name が欠落していると UsersConfigError になること。"""
    path = write_config(tmp_path, f'[[users]]\napi_key = "{ALICE_KEY}"\n')
    with pytest.raises(UsersConfigError):
        load_users(path)


def test_load_users_missing_api_key_raises(tmp_path: Path) -> None:
    """api_key が欠落していると UsersConfigError になること。"""
    path = write_config(tmp_path, '[[users]]\nname = "alice"\n')
    with pytest.raises(UsersConfigError):
        load_users(path)


def test_load_users_empty_name_raises(tmp_path: Path) -> None:
    """設定の name が空文字だと UsersConfigError になること。"""
    path = write_config(tmp_path, f'[[users]]\nname = ""\napi_key = "{ALICE_KEY}"\n')
    with pytest.raises(UsersConfigError):
        load_users(path)


def test_load_users_empty_api_key_raises(tmp_path: Path) -> None:
    """api_key が空文字だと UsersConfigError になること。"""
    path = write_config(tmp_path, '[[users]]\nname = "alice"\napi_key = ""\n')
    with pytest.raises(UsersConfigError):
        load_users(path)


def test_load_users_non_string_name_raises(tmp_path: Path) -> None:
    """設定の name が文字列でないと UsersConfigError になること。"""
    path = write_config(tmp_path, f'[[users]]\nname = 1\napi_key = "{ALICE_KEY}"\n')
    with pytest.raises(UsersConfigError):
        load_users(path)


def test_load_users_non_string_api_key_raises(tmp_path: Path) -> None:
    """api_key が文字列でないと UsersConfigError になること。"""
    path = write_config(tmp_path, '[[users]]\nname = "alice"\napi_key = 123\n')
    with pytest.raises(UsersConfigError):
        load_users(path)


def test_load_users_duplicate_name_raises(tmp_path: Path) -> None:
    """設定の name が重複していると UsersConfigError になること。"""
    text = (
        f'[[users]]\nname = "alice"\napi_key = "{ALICE_KEY}"\n'
        f'[[users]]\nname = "alice"\napi_key = "{BOB_KEY}"\n'
    )
    with pytest.raises(UsersConfigError):
        load_users(write_config(tmp_path, text))


def test_load_users_duplicate_api_key_raises(tmp_path: Path) -> None:
    """api_key が重複していると UsersConfigError になること。"""
    text = (
        f'[[users]]\nname = "alice"\napi_key = "{ALICE_KEY}"\n'
        f'[[users]]\nname = "bob"\napi_key = "{ALICE_KEY}"\n'
    )
    with pytest.raises(UsersConfigError):
        load_users(write_config(tmp_path, text))


def test_load_users_invalid_utf8_raises_users_config_error(tmp_path: Path) -> None:
    """UTF-8 として読めない設定は、内容を含まない UsersConfigError になること。"""
    path = tmp_path / "users.toml"
    path.write_bytes(b"\xff\xfe\x00")
    with pytest.raises(UsersConfigError) as exc_info:
        load_users(path)
    message = str(exc_info.value)
    assert "\\xff" not in message
    assert "\xff" not in message
    assert "0xff" not in message
    assert "position" not in message


def test_load_users_duplicate_api_key_message_hides_key(tmp_path: Path) -> None:
    """api_key 重複のエラーメッセージに、重複したキーの値が含まれないこと。"""
    text = (
        f'[[users]]\nname = "alice"\napi_key = "{ALICE_KEY}"\n'
        f'[[users]]\nname = "bob"\napi_key = "{ALICE_KEY}"\n'
    )
    with pytest.raises(UsersConfigError) as exc_info:
        load_users(write_config(tmp_path, text))
    assert ALICE_KEY not in str(exc_info.value)


def test_users_config_error_is_value_error() -> None:
    """UsersConfigError が ValueError のサブクラスであること。"""
    assert issubclass(UsersConfigError, ValueError)


# --- 設定ファイルの場所 ---


def test_get_users_path_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """環境変数がないと config/users.toml が返ること。"""
    monkeypatch.delenv("USERS_CONFIG_PATH", raising=False)
    assert get_users_path() == Path("config/users.toml")


def test_get_users_path_uses_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    """USERS_CONFIG_PATH があればその値が返ること。"""
    monkeypatch.setenv("USERS_CONFIG_PATH", "dummy/users.toml")
    assert get_users_path() == Path("dummy/users.toml")


# --- 起動時の検証 ---


def test_startup_fails_with_invalid_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """不正な設定だとアプリの起動が UsersConfigError で失敗すること。"""
    path = write_config(tmp_path, "users = []\n")
    monkeypatch.setenv("USERS_CONFIG_PATH", str(path))
    with pytest.raises(UsersConfigError), TestClient(app):
        pass


def test_startup_fails_with_missing_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """設定ファイルが存在しないとアプリの起動が UsersConfigError で失敗すること。"""
    monkeypatch.setenv("USERS_CONFIG_PATH", str(tmp_path / "nothing.toml"))
    with pytest.raises(UsersConfigError), TestClient(app):
        pass


def test_startup_succeeds_with_valid_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """有効な設定（ダミーのキー）ならアプリが起動できること。"""
    path = write_config(tmp_path, VALID_TOML)
    monkeypatch.setenv("USERS_CONFIG_PATH", str(path))
    with TestClient(app, headers={"X-API-Key": ALICE_KEY}) as client:
        response = client.get("/add", params={"a": 1, "b": 2})
    assert response.status_code == 200


# --- 401 ---


def test_missing_header_returns_401(anon_client: TestClient) -> None:
    """X-API-Key ヘッダーがないと 401 になること。"""
    response = anon_client.get("/add", params={"a": 1, "b": 2})
    assert response.status_code == 401
    assert response.json() == UNAUTHORIZED_BODY


def test_wrong_key_returns_401(anon_client: TestClient) -> None:
    """キーが一致しないと 401 になること。"""
    response = anon_client.get(
        "/add", params={"a": 1, "b": 2}, headers={"X-API-Key": "wrong-key"}
    )
    assert response.status_code == 401
    assert response.json() == UNAUTHORIZED_BODY


def test_empty_key_returns_401(anon_client: TestClient) -> None:
    """空のキーだと 401 になること。"""
    response = anon_client.get(
        "/add", params={"a": 1, "b": 2}, headers={"X-API-Key": ""}
    )
    assert response.status_code == 401
    assert response.json() == UNAUTHORIZED_BODY


@pytest.mark.parametrize("key", [f" {ALICE_KEY}", f"{ALICE_KEY} ", f" {ALICE_KEY} "])
def test_key_with_surrounding_whitespace_returns_401(
    anon_client: TestClient, key: str
) -> None:
    """前後に空白のあるキーは取り除かれず、不一致として 401 になること。"""
    response = anon_client.get(
        "/add", params={"a": 1, "b": 2}, headers={"X-API-Key": key}
    )
    assert response.status_code == 401
    assert response.json() == UNAUTHORIZED_BODY


def test_non_ascii_key_returns_401_not_500(anon_client: TestClient) -> None:
    """ASCII 以外を含むキー（バイト列で送信）が 500 ではなく 401 になること。"""
    response = anon_client.get(
        "/add",
        params={"a": 1, "b": 2},
        headers={"X-API-Key": "キー-é".encode()},
    )
    assert response.status_code == 401
    assert response.json() == UNAUTHORIZED_BODY


def test_missing_header_and_wrong_key_responses_are_identical(
    anon_client: TestClient,
) -> None:
    """ヘッダーなしとキー違いで、ステータスも本文も同じであること。"""
    missing = anon_client.get("/add", params={"a": 1, "b": 2})
    wrong = anon_client.get(
        "/add", params={"a": 1, "b": 2}, headers={"X-API-Key": "wrong-key"}
    )
    assert missing.status_code == wrong.status_code
    assert missing.json() == wrong.json()


def test_401_body_does_not_contain_key(anon_client: TestClient) -> None:
    """401 の本文に送信したキーが含まれないこと。"""
    sent = "secret-wrong-key-123"
    response = anon_client.get(
        "/add", params={"a": 1, "b": 2}, headers={"X-API-Key": sent}
    )
    assert response.status_code == 401
    assert sent not in response.text


# --- 認証成功 ---


@pytest.mark.parametrize(
    ("path", "a", "b", "expected"),
    [
        ("/add", 1, 2, 3),
        ("/subtract", 5, 3, 2),
        ("/multiply", 3, 4, 12),
        ("/divide", 6, 3, 2),
    ],
)
def test_valid_key_allows_every_endpoint(
    anon_client: TestClient, path: str, a: int, b: int, expected: int
) -> None:
    """有効なキーなら 4 つのエンドポイントがこれまでどおりの結果を返すこと。"""
    response = anon_client.get(
        path, params={"a": a, "b": b}, headers={"X-API-Key": ALICE_KEY}
    )
    assert response.status_code == 200
    assert response.json() == {"result": expected}


def test_other_users_valid_key_is_accepted(anon_client: TestClient) -> None:
    """別のユーザーの有効なキーでも認証に通ること。"""
    response = anon_client.get(
        "/add", params={"a": 1, "b": 2}, headers={"X-API-Key": BOB_KEY}
    )
    assert response.status_code == 200
    assert response.json() == {"result": 3}


# --- 処理順序 ---


def test_unauthenticated_invalid_input_returns_401_not_422(
    anon_client: TestClient,
) -> None:
    """未認証で不正な入力（a=0）を送ると 422 ではなく 401 になること。"""
    response = anon_client.get("/add", params={"a": 0, "b": 2})
    assert response.status_code == 401
    assert response.json() == UNAUTHORIZED_BODY


def test_authenticated_invalid_input_returns_422(anon_client: TestClient) -> None:
    """認証済みで不正な入力（a=0）を送ると 422 になること。"""
    response = anon_client.get(
        "/add", params={"a": 0, "b": 2}, headers={"X-API-Key": ALICE_KEY}
    )
    assert response.status_code == 422
    assert "detail" in response.json()


# --- 異常なキーの扱い ---


@pytest.mark.parametrize(
    "key",
    [b"a" * 100_000, b"abc\x01def", b"\xff\xfe"],
    ids=["100k-chars", "control-char", "latin1-bytes"],
)
def test_abnormal_key_returns_401_not_500(key: bytes) -> None:
    """極端に長い・制御文字を含む・非 UTF-8 のキーが 500 ではなく 401 になること。"""
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/add", params={"a": 1, "b": 2}, headers={"X-API-Key": key})
    assert response.status_code == 401
    assert response.json() == UNAUTHORIZED_BODY


def test_401_headers_do_not_contain_key(anon_client: TestClient) -> None:
    """401 のレスポンスヘッダーに送信したキーの値が含まれないこと。"""
    sent = "secret-wrong-key-123"
    response = anon_client.get(
        "/add", params={"a": 1, "b": 2}, headers={"X-API-Key": sent}
    )
    assert response.status_code == 401
    assert all(sent not in value for value in response.headers.values())


# --- API 構成の非公開 ---


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
@pytest.mark.parametrize("with_key", [False, True], ids=["no-key", "with-key"])
def test_docs_endpoints_are_disabled(
    anon_client: TestClient, path: str, with_key: bool
) -> None:
    """/docs・/redoc・/openapi.json が、キーの有無によらず 404 になること。"""
    headers = {"X-API-Key": ALICE_KEY} if with_key else {}
    response = anon_client.get(path, headers=headers)
    assert response.status_code == 404
