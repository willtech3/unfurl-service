# Multi-stage Dockerfile for Instagram unfurl service with Playwright
# Designed to resolve Docker build issues by separating build and runtime environments

# =====================================================
# Build Stage: Use official Playwright image for browser installation
# =====================================================
# Using the official Playwright image ensures compatibility and includes all
# necessary system dependencies (apt-get, etc.) for browser installation
FROM mcr.microsoft.com/playwright/python:v1.45.0-jammy as builder

# Set environment variables for build stage
ENV PYTHONUNBUFFERED=1
ENV DOCKER_BUILDKIT=1
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Copy requirements and install Python dependencies
COPY requirements-docker.txt /tmp/requirements-docker.txt

# Install Python packages to a temporary directory
RUN echo "Installing Python packages in build stage..." && \
    pip install --no-cache-dir --upgrade pip setuptools wheel && \
    # Install packages to /app directory which we'll copy to runtime stage
    pip install --no-cache-dir --prefer-binary --target /app -r /tmp/requirements-docker.txt && \
    echo "Python packages installed successfully in build stage"

# Install Playwright browsers (this will work properly with apt-get available)
RUN echo "Installing Playwright browsers in build stage..." && \
    cd /app && \
    PYTHONPATH=/app python -m playwright install chromium --with-deps && \
    echo "Browser installation completed successfully"

# =====================================================
# Runtime Stage: Clean Lambda environment
# =====================================================
FROM public.ecr.aws/lambda/python:3.12-arm64

# Set environment variables for runtime
ENV PYTHONUNBUFFERED=1
ENV DOCKER_BUILDKIT=1
ENV PLAYWRIGHT_BROWSERS_PATH=/var/task/playwright-browsers
ENV PYTHONPATH=/var/task
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=0

# Install only runtime dependencies (no build tools)
RUN dnf update -y && \
    dnf install -y \
        # Basic utilities
        wget \
        ca-certificates \
        findutils \
        binutils \
        tar \
        gzip \
        unzip \
        # Core X11 and graphics libraries for Playwright
        xorg-x11-server-Xvfb \
        nss \
        atk \
        gtk3 \
        cups-libs \
        dbus-glib \
        libdrm \
        libXcomposite \
        libXdamage \
        libXrandr \
        libxkbcommon \
        libXScrnSaver \
        # Audio support
        alsa-lib \
        # Font support
        fontconfig \
        liberation-fonts \
        # Additional dependencies for browser automation
        mesa-libgbm && \
    dnf clean all && \
    rm -rf /var/cache/dnf

# Copy installed Python packages from build stage
COPY --from=builder /app ${LAMBDA_TASK_ROOT}

# Copy Playwright browsers from build stage to Lambda task root
# The browsers were installed in the build stage using the official Playwright image
COPY --from=builder /ms-playwright ${PLAYWRIGHT_BROWSERS_PATH}

# Verify Playwright installation and version consistency
RUN echo "Verifying Playwright installation..." && \
    cd ${LAMBDA_TASK_ROOT} && \
    PYTHONPATH=${LAMBDA_TASK_ROOT} python -c \
    "import sys; print('Python version:', sys.version); print('Python path:', sys.path[:3]); import playwright; version = getattr(playwright, '__version__', 'unknown'); print('✅ Playwright imported successfully, version:', version); print('Playwright location:', playwright.__file__); \
    import sys; \
    if version == 'unknown': \
        print('❌ Warning: Playwright version is unknown, this may cause import issues'); \
        sys.exit(1); \
    elif not version.startswith('1.45'): \
        print(f'❌ Warning: Expected Playwright v1.45.x, got {version}'); \
        sys.exit(1); \
    else: \
        print('✅ Playwright version check passed')" || \
    (echo "❌ Playwright import or version check failed" && exit 1)

# Verify browser installation (browsers are now copied from build stage)
RUN echo "Verifying browser installation..." && \
    echo "Browser installation completed, verifying..." && \
    ls -la ${PLAYWRIGHT_BROWSERS_PATH}/ && \
    echo "Searching for Chromium files..." && \
    find ${PLAYWRIGHT_BROWSERS_PATH} -name "*chromium*" -type d && \
    find ${PLAYWRIGHT_BROWSERS_PATH} -name "chrome*" -type f | head -10

# Verify browser installation and set permissions
RUN echo "Setting browser permissions and verifying installation..." && \
    find ${PLAYWRIGHT_BROWSERS_PATH} -type f -name "chrome*" -exec chmod +x {} \; && \
    find ${PLAYWRIGHT_BROWSERS_PATH} -type f -name "chromium*" -exec chmod +x {} \; && \
    # Test if we can find the browser executable
    CHROMIUM_EXECUTABLE=$(find ${PLAYWRIGHT_BROWSERS_PATH} -name "chrome" -type f | head -1) && \
    if [ -n "$CHROMIUM_EXECUTABLE" ]; then \
        echo "✅ Found Chromium executable at: $CHROMIUM_EXECUTABLE"; \
        ls -la "$CHROMIUM_EXECUTABLE"; \
    else \
        echo "❌ Chromium executable not found"; \
        echo "Contents of browsers directory:"; \
        find ${PLAYWRIGHT_BROWSERS_PATH} -type f | head -20; \
        exit 1; \
    fi

# Test Playwright functionality
RUN echo "Testing Playwright functionality..." && \
    cd ${LAMBDA_TASK_ROOT} && \
    PLAYWRIGHT_BROWSERS_PATH=${PLAYWRIGHT_BROWSERS_PATH} \
    PYTHONPATH=${LAMBDA_TASK_ROOT} \
    python -c "from playwright.async_api import async_playwright; print('✅ Playwright imports working')" && \
    echo "✅ Basic Playwright test passed"

# Optimize and clean up
RUN echo "Optimizing installation..." && \
    # Strip debug symbols from shared libraries to reduce size
    find ${LAMBDA_TASK_ROOT} -type f -name "*.so" -exec strip {} \; 2>/dev/null || true && \
    # Remove unnecessary files
    find ${LAMBDA_TASK_ROOT} -type f -name "*.pyc" -delete && \
    find ${LAMBDA_TASK_ROOT} -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true && \
    # Verify final state
    echo "Final verification..." && \
    du -sh ${PLAYWRIGHT_BROWSERS_PATH} && \
    echo "Installation optimization completed"

# Copy application source code
COPY src/ ${LAMBDA_TASK_ROOT}/

# Copy test script for Playwright validation
COPY test_playwright_fix.py ${LAMBDA_TASK_ROOT}/

# Final verification that everything is working
RUN echo "Final Playwright verification..." && \
    cd ${LAMBDA_TASK_ROOT} && \
    PLAYWRIGHT_BROWSERS_PATH=${PLAYWRIGHT_BROWSERS_PATH} \
    PYTHONPATH=${LAMBDA_TASK_ROOT} \
    python test_playwright_fix.py && \
    echo "Running scraper module verification..." && \
    PLAYWRIGHT_BROWSERS_PATH=${PLAYWRIGHT_BROWSERS_PATH} \
    PYTHONPATH=${LAMBDA_TASK_ROOT} \
    python -c "from unfurl_processor.scrapers.playwright_scraper import PLAYWRIGHT_AVAILABLE; print('PLAYWRIGHT_AVAILABLE from scraper:', PLAYWRIGHT_AVAILABLE); exit(0 if PLAYWRIGHT_AVAILABLE else 1)" && \
    echo "✅ All verifications passed"

# Set Lambda handler
CMD ["unfurl_processor.entrypoint.lambda_handler"]