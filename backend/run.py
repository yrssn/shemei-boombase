"""本地启动入口：python run.py  （等价于 uvicorn app.main:app --reload）

可用环境变量：HOST（默认 0.0.0.0）、PORT（默认 8000）、RELOAD（默认 1，设为 0 关闭热重载）
"""
import os
import sys
from pathlib import Path

os.chdir(Path(__file__).resolve().parent)
sys.path.insert(0, os.getcwd())

try:
    import uvicorn
except ImportError:
    sys.exit("缺少依赖，请先执行：pip install -r requirements.txt")

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("RELOAD", "1") == "1",
    )
