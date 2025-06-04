# Robust Dockerfile for Instagram unfurl service with Playwright
# Designed to resolve Playwright installation issues in Lambda

FROM public.ecr.aws/lambda/python:3.12-arm64

# Set environment variables early
ENV PYTHONUNBUFFERED=1
ENV DOCKER_BUILDKIT=1
ENV PLAYWRIGHT_BROWSERS_PATH=/var/task/playwright-browsers
ENV PYTHONPATH=/var/task
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=0

# Install comprehensive system dependencies for Playwright
RUN dnf update -y && \
    dnf install -y \
        wget \
        curl \
        ca-certificates \
        findutils \
        binutils \
        tar \
        gzip \
        unzip \
        # Core X11 and graphics libraries
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
        libXss \
        # Audio support
        alsa-lib \
        # Font support
        fontconfig \
        liberation-fonts \
        # Additional dependencies for browser automation
        mesa-libgbm \
        libgtk-3-0 \
        libnss3 \
        libxrandr2 \
        libdrm2 \
        libxkbcommon0 \
        libxcomposite1 \
        libxdamage1 \
        libxss1 \
        libasound2 && \
    dnf clean all && \
    rm -rf /var/cache/dnf

# Copy requirements and install Python dependencies with verbose output
COPY requirements-docker.txt /tmp/requirements-docker.txt

# Install Python packages with detailed logging
RUN echo "Installing Python packages..." && \
    pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --verbose --target ${LAMBDA_TASK_ROOT} -r /tmp/requirements-docker.txt && \
    echo "Python packages installed successfully"

# Verify Playwright installation
RUN echo "Verifying Playwright installation..." && \
    cd ${LAMBDA_TASK_ROOT} && \
    PYTHONPATH=${LAMBDA_TASK_ROOT} python -c \
    "import sys; print('Python version:', sys.version); print('Python path:', sys.path[:3]); import playwright; print('✅ Playwright imported successfully, version:', getattr(playwright, '__version__', 'unknown')); print('Playwright location:', playwright.__file__)" || \
    (echo "❌ Playwright import failed" && exit 1)

# Install Playwright browsers with comprehensive logging and error handling
RUN echo "Installing Playwright browsers..." && \
    cd ${LAMBDA_TASK_ROOT} && \
    mkdir -p ${PLAYWRIGHT_BROWSERS_PATH} && \
    PLAYWRIGHT_BROWSERS_PATH=${PLAYWRIGHT_BROWSERS_PATH} \
    PYTHONPATH=${LAMBDA_TASK_ROOT} \
    python -m playwright install --help && \
    echo "Installing Chromium browser..." && \
    PLAYWRIGHT_BROWSERS_PATH=${PLAYWRIGHT_BROWSERS_PATH} \
    PYTHONPATH=${LAMBDA_TASK_ROOT} \
    python -m playwright install chromium --with-deps --verbose && \
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

# Copy debug script for testing (if it exists)
# COPY test_playwright_debug.py ${LAMBDA_TASK_ROOT}/

# Final verification that everything is working
RUN echo "Final Playwright verification..." && \
    cd ${LAMBDA_TASK_ROOT} && \
    PLAYWRIGHT_BROWSERS_PATH=${PLAYWRIGHT_BROWSERS_PATH} \
    PYTHONPATH=${LAMBDA_TASK_ROOT} \
    python -c "from unfurl_processor.scrapers.playwright_scraper import PLAYWRIGHT_AVAILABLE; print('PLAYWRIGHT_AVAILABLE from scraper:', PLAYWRIGHT_AVAILABLE); exit(0 if PLAYWRIGHT_AVAILABLE else 1)" && \
    echo "✅ All verifications passed"

# Set Lambda handler
CMD ["unfurl_processor.entrypoint.lambda_handler"]