#!/bin/bash

# VidPPT 测试运行脚本

set -e

echo "======================================"
echo "  VidPPT 测试套件"
echo "======================================"
echo ""

# 颜色定义
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 检查依赖
echo -e "${BLUE}检查测试依赖...${NC}"
python -c "import pytest; import pytest_asyncio; import pytest_cov" 2>/dev/null || {
    echo "安装测试依赖..."
    pip install -e ".[dev]"
}

echo ""
echo -e "${BLUE}运行单元测试...${NC}"
python -m pytest tests/unit/ -v --tb=short

echo ""
echo -e "${GREEN}✓ 所有测试通过！${NC}"

# 生成覆盖率报告（可选）
if [ "$1" = "--coverage" ] || [ "$1" = "-c" ]; then
    echo ""
    echo -e "${BLUE}生成覆盖率报告...${NC}"
    python -m pytest tests/unit/ --cov=vidppt --cov-report=term-missing --cov-report=html
    echo ""
    echo -e "${GREEN}HTML 覆盖率报告已生成到 htmlcov/index.html${NC}"
fi

echo ""
echo "======================================"
echo "  测试完成"
echo "======================================"
