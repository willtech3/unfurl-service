# 🚀 Deployment Speed Optimization Guide

This document explains the deployment optimization strategies available for the unfurl-service.

## 📊 Performance Comparison

| Deployment Mode | Time | Use Case | Compatibility |
|----------------|------|----------|---------------|
| **Standard** | ~12-15 min | CI/CD, Production | ✅ Universal |
| **Fast** | ~2-4 min | Local Development | 🏠 Local Only |

## 🛠️ Standard Deployment (Default)

**What it is:** The original self-contained Docker build that downloads all dependencies including Playwright browsers during each deployment.

**When to use:**
- ✅ CI/CD pipelines
- ✅ Production deployments  
- ✅ Team members without ECR access
- ✅ First-time setup

**How to use:**
```bash
# Standard deployment (always works)
cdk deploy
```

**Characteristics:**
- 🔄 Self-contained: No external dependencies
- 🌍 Universal: Works in any environment
- 📦 Downloads 167MB Playwright browsers each time
- ⏱️ ~12-15 minutes per deployment

## ⚡ Fast Deployment (Optional)

**What it is:** Uses a pre-built base image with Playwright browsers already installed, eliminating the slow browser download step.

**When to use:**
- 🏠 Local development iterations
- 🔧 Frequent testing deployments
- ⚡ When you need rapid feedback cycles

**Prerequisites:**
- AWS ECR access
- Docker BuildKit enabled
- Base image built and pushed to ECR

**Setup (One-time):**
```bash
# Build a base image with Playwright browsers and push to ECR (example)
docker build -f Dockerfile.base -t unfurl-base:latest --platform linux/arm64 .
docker tag unfurl-base:latest <ACCOUNT>.dkr.ecr.<REGION>.amazonaws.com/unfurl-base:latest
docker push <ACCOUNT>.dkr.ecr.<REGION>.amazonaws.com/unfurl-base:latest
```

**How to use:**
```bash
# After setup, deploy normally (now uses fast mode)
cdk deploy
```

**Characteristics:**
- ⚡ 70-80% faster deployments
- 📦 Pre-built base image with browsers
- 🏠 Local development only
- 🔧 Requires ECR repository

## 🔄 Switching Between Modes

### Activate Fast Mode
Switch your Dockerfile `FROM` to the ECR base image:
```dockerfile
FROM <ACCOUNT>.dkr.ecr.<REGION>.amazonaws.com/unfurl-base:latest
```

### Revert to Standard Mode
Switch your Dockerfile back to the standard Lambda base image.

## 🏗️ How Fast Deployment Works

### 1. Base Image Strategy
- **One-time build:** Creates base image with Playwright pre-installed
- **ECR storage:** Base image stored in your private ECR repository
- **Reusable:** Base image used for all subsequent fast deployments

### 2. Fast Dockerfile
```dockerfile
# Uses pre-built base instead of Lambda base image
FROM your-account.dkr.ecr.region.amazonaws.com/unfurl-base:latest

# Only installs application dependencies (fast)
COPY requirements-docker.txt /tmp/
RUN pip install --no-cache-dir --target ${LAMBDA_TASK_ROOT} -r /tmp/requirements-docker.txt

# Copy source code
COPY src/ ${LAMBDA_TASK_ROOT}/
```

### 3. Speed Improvements
- ❌ **Eliminated:** 167MB Playwright browser download
- ❌ **Eliminated:** System dependency installation
- ❌ **Eliminated:** Playwright setup and configuration
- ✅ **Only:** Application dependency installation (~30-60 seconds)

## 🔧 Technical Details

### CDK Optimizations Applied
- **BuildKit caching:** `BUILDKIT_INLINE_CACHE=1` for layer reuse
- **Build context exclusion:** Removes unnecessary files from Docker context
- **Asset optimization:** Faster CDK asset bundling

### Base Image Contents
- **Base:** AWS Lambda Python 3.12 ARM64
- **System deps:** `wget`, `ca-certificates`, `findutils`
- **Playwright:** Version 1.45.0 with chromium browser
- **Path:** Browsers in `/root/.cache/ms-playwright`

### ECR Repository
- **Name:** `unfurl-base`
- **Tag:** `latest`
- **Platform:** `linux/arm64`
- **Size:** ~500MB (one-time download)

## 🚨 Important Notes

### CI/CD Compatibility
- **CI builds:** Always use standard Dockerfile (automatic)
- **Local builds:** Can use either mode
- **Production:** Recommend standard mode for consistency

### Maintenance
- **Base image updates:** Rebuild when Playwright version changes
- **Cost:** ECR storage costs (~$0.10/GB/month)
- **Security:** Base image uses same Lambda base as standard mode

### Troubleshooting

**If fast deployment fails:**
```bash
# Check ECR connectivity
aws ecr describe-repositories --repository-names unfurl-base
```

**If base image is missing:**
```bash
# Rebuild base image
docker build -f Dockerfile.base -t unfurl-base:latest --platform linux/arm64 .
docker tag unfurl-base:latest YOUR_ACCOUNT.dkr.ecr.REGION.amazonaws.com/unfurl-base:latest
docker push YOUR_ACCOUNT.dkr.ecr.REGION.amazonaws.com/unfurl-base:latest
```

## 🎯 Recommendations

### For Local Development
1. Use fast deployment for rapid iteration
2. Keep standard mode for final testing before CI
3. Rebuild base image monthly or when Playwright updates

### For Teams
1. Share base image setup across team members
2. Document ECR repository access requirements
3. Use standard mode for all CI/CD pipelines

### For Production
1. Always use standard deployment mode
2. Consider fast mode for staging environments
3. Monitor ECR costs if using fast mode extensively

---

**Summary:** Fast deployment provides 70-80% speed improvement for local development while maintaining full CI/CD compatibility through the standard deployment mode.
