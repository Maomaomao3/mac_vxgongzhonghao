"""所有配置集中于此；.app 使用用户目录中的 config.json 覆盖这些默认值。"""
from pathlib import Path
import json

AI_BASE_URL = 'https://api.deepseek.com'
AI_MODEL = 'deepseek-chat'  # 可改为你的服务实际支持的模型
AI_API_KEY = ''
PEXELS_API_KEY = ''
WECHAT_APP_ID = ''
WECHAT_APP_SECRET = ''
IMAGE_SOURCE = "original"  # original / pexels / none
AUTHOR = ''
TIMEOUT = 60
MAX_SOURCE_CHARS = 40000
DATA_DIR = Path.home() / 'Library/Application Support/WeChatAIStudio'
CONFIG_PATH = DATA_DIR / 'config.json'
DEFAULTS = {k: v for k, v in globals().copy().items() if k in (
    'AI_BASE_URL', 'AI_MODEL', 'AI_API_KEY', 'PEXELS_API_KEY',
    'WECHAT_APP_ID', 'WECHAT_APP_SECRET', 'IMAGE_SOURCE', 'AUTHOR')}


def ensure_config():
    DATA_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(json.dumps(DEFAULTS, ensure_ascii=False, indent=2))
        CONFIG_PATH.chmod(0o600)


def load_config():
    ensure_config()
    try:
        data = json.loads(CONFIG_PATH.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f'配置 JSON 格式错误：第 {exc.lineno} 行，第 {exc.colno} 列。') from None
    if not isinstance(data, dict):
        raise ValueError('配置文件顶层必须是 JSON 对象。')
    settings = {**DEFAULTS, **data}
    settings.pop('IMAGE_COUNT', None)  # 兼容旧配置，数量字段不再使用
    if settings['IMAGE_SOURCE'] not in ('original', 'pexels', 'none'):
        raise ValueError('IMAGE_SOURCE 必须为 original、pexels 或 none。')
    return settings
