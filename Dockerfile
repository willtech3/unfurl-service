# Multi-stage Docker build for high-performance Lambda with Playwright
# Optimized for fast cold starts and ARM64 performance

# Stage 1: Playwright browser installation
FROM public.ecr.aws/lambda/python:3.12-arm64 AS playwright-base

# Install minimal system dependencies with better error handling
RUN dnf update -y && \
    dnf install -y wget ca-certificates && \
    dnf clean all && \
    rm -rf /var/cache/dnf

# Install core Python dependencies first (layer caching optimization)
COPY requirements-docker.txt /tmp/
RUN pip install --no-cache-dir --target ${LAMBDA_TASK_ROOT} \
    $(grep -E '^(aws-lambda-powertools|boto3|slack-sdk|requests|beautifulsoup4|lxml)' /tmp/requirements-docker.txt)

# Install Playwright and browser binaries
RUN pip install --no-cache-dir --target ${LAMBDA_TASK_ROOT} playwright==1.45.0 playwright-stealth==1.0.6

# Install Playwright browsers with optimizations (cache-bust v4)
ENV PLAYWRIGHT_BROWSERS_PATH=${LAMBDA_TASK_ROOT}/playwright-browsers
RUN cd ${LAMBDA_TASK_ROOT} && \
    python -m playwright install chromium

# Optimize browser binaries for Lambda
RUN find ${LAMBDA_TASK_ROOT} -type f -name "*.so" -exec strip {} \; 2>/dev/null || true && \
    find ${LAMBDA_TASK_ROOT} -type f -name "chrome*" -exec chmod +x {} \; && \
    find ${LAMBDA_TASK_ROOT} -type f -name "chromium*" -exec chmod +x {} \;

# Stage 2: Application layer with remaining dependencies
FROM public.ecr.aws/lambda/python:3.12-arm64 AS final

# Copy Playwright and core dependencies from previous stage
COPY --from=playwright-base ${LAMBDA_TASK_ROOT} ${LAMBDA_TASK_ROOT}

# Install remaining dependencies for performance
RUN pip install --no-cache-dir --target ${LAMBDA_TASK_ROOT} \
    uvloop==0.19.0 \
    httpx==0.26.0

# Copy application source code
COPY src/ ${LAMBDA_TASK_ROOT}/

# Set the Lambda handler
CMD ["unfurl_processor.entrypoint.lambda_handler"]
