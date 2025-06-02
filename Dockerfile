# Single optimized Dockerfile for Instagram unfurl service
# Designed for cross-platform builds with ARM64 Lambda

FROM public.ecr.aws/lambda/python:3.12-arm64

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV DOCKER_BUILDKIT=1
ENV PLAYWRIGHT_BROWSERS_PATH=/var/task/playwright-browsers

# Install system dependencies needed for Playwright
RUN dnf update -y && \
    dnf install -y \
        wget \
        ca-certificates \
        findutils \
        binutils \
        nss \
        atk \
        gtk3 \
        libdrm \
        libXcomposite \
        libXdamage \
        libXrandr \
        mesa-libgbm \
        alsa-lib && \
    dnf clean all && \
    rm -rf /var/cache/dnf

# Copy requirements and install Python dependencies
COPY requirements-docker.txt /tmp/requirements-docker.txt
RUN pip install --no-cache-dir --target ${LAMBDA_TASK_ROOT} -r /tmp/requirements-docker.txt

# Install Playwright and browser
RUN pip install --no-cache-dir --target ${LAMBDA_TASK_ROOT} \
    playwright-stealth==1.0.6

# Install Playwright browsers
RUN cd ${LAMBDA_TASK_ROOT} && \
    python -m playwright install chromium

# Optimize browser binaries for Lambda
RUN find ${LAMBDA_TASK_ROOT} -type f -name "*.so" -exec strip {} \; 2>/dev/null || true && \
    find ${LAMBDA_TASK_ROOT} -type f -name "chrome*" -exec chmod +x {} \; && \
    find ${LAMBDA_TASK_ROOT} -type f -name "chromium*" -exec chmod +x {} \;

# Copy application source code
COPY src/ ${LAMBDA_TASK_ROOT}/

# Set Lambda handler
CMD ["unfurl_processor.entrypoint.lambda_handler"]
