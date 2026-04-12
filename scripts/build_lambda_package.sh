#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="${ROOT_DIR}/build/lambda"
PACKAGE_DIR="${BUILD_DIR}/package"
DIST_DIR="${ROOT_DIR}/dist"

rm -rf "${BUILD_DIR}" "${DIST_DIR}"
mkdir -p "${PACKAGE_DIR}" "${DIST_DIR}"

docker run --rm \
  --platform linux/arm64 \
  -u "$(id -u):$(id -g)" \
  -v "${ROOT_DIR}:/workspace" \
  -w /workspace \
  public.ecr.aws/lambda/python:3.11 \
  /bin/sh -lc "python -m pip install --no-cache-dir -r requirements.txt -t build/lambda/package"

cp -R "${ROOT_DIR}/src/." "${PACKAGE_DIR}/"

cd "${PACKAGE_DIR}"
zip -qr "${DIST_DIR}/lambda.zip" .

echo "Built ${DIST_DIR}/lambda.zip"
