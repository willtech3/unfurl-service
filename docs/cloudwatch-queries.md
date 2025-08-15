# CloudWatch Metrics and Queries for Instagram Unfurl Service

## 📊 Available Metrics

All metrics are published to the `UnfurlService/Scrapers` namespace.

### Core Success/Failure Metrics

| Metric Name | Description | Dimensions |
|-------------|-------------|------------|
| `ScraperSuccess` | Successful scraper executions | `Scraper` (playwright, http) |
| `ScraperFailure` | Failed scraper executions | `Scraper` |
| `ScraperException` | Scraper exceptions/crashes | `Scraper` |
| `AllScrapersFailed` | When all scrapers fail for a URL | None |
| `BestQualityScraper` | Which scraper provided the best result | `Scraper` |

### Performance Metrics

| Metric Name | Description | Dimensions | Unit |
|-------------|-------------|------------|------|
| `ScraperResponseTime` | Individual scraper response times | `Scraper` | Milliseconds |
| `ScrapingTime` | Total time to process all scrapers | None | Milliseconds |
| `QualityScore` | Quality score for each result | `Scraper` | Count |

### Content Quality Metrics

| Metric Name | Description | Dimensions |
|-------------|-------------|------------|
| `ContentType` | Type of content found | `Type` (video, photo), `Scraper` |
| `QualityFactor` | Specific quality factors detected | `Factor`, `Scraper` |

#### Quality Factors
- `has_caption` - Post has caption text
- `has_description` - Post has description
- `has_title` - Post has title
- `has_video` - Post contains video
- `has_multiple_images` - Post has multiple images
- `has_author` - Author information available
- `has_engagement` - Like/comment counts available
- `is_high_quality` - High-resolution media detected

## 🔍 Useful CloudWatch Queries

### 1. Scraper Success Rates (last 24 hours)
```
SELECT Scraper, SUM(ScraperSuccess) as Successes, SUM(ScraperFailure) as Failures,
       (SUM(ScraperSuccess) / (SUM(ScraperSuccess) + SUM(ScraperFailure))) * 100 as SuccessRate
FROM SCHEMA("UnfurlService/Scrapers", Scraper)
WHERE MetricName IN ('ScraperSuccess', 'ScraperFailure')
GROUP BY Scraper
ORDER BY SuccessRate DESC
```

### 2. Average Response Times by Scraper
```
SELECT Scraper, AVG(ScraperResponseTime) as AvgResponseTime, 
       MAX(ScraperResponseTime) as MaxResponseTime,
       MIN(ScraperResponseTime) as MinResponseTime
FROM SCHEMA("UnfurlService/Scrapers", Scraper)
WHERE MetricName = 'ScraperResponseTime'
GROUP BY Scraper
ORDER BY AvgResponseTime
```

### 3. Quality Score Distribution
```
SELECT Scraper, AVG(QualityScore) as AvgQuality,
       MAX(QualityScore) as MaxQuality,
       COUNT(*) as TotalResults
FROM SCHEMA("UnfurlService/Scrapers", Scraper)
WHERE MetricName = 'QualityScore'
GROUP BY Scraper
ORDER BY AvgQuality DESC
```

### 4. Video vs Photo Content Distribution
```
SELECT Type, Scraper, COUNT(*) as Count
FROM SCHEMA("UnfurlService/Scrapers", Type, Scraper)
WHERE MetricName = 'ContentType'
GROUP BY Type, Scraper
ORDER BY Count DESC
```

### 5. Most Common Quality Factors
```
SELECT Factor, COUNT(*) as Frequency,
       (COUNT(*) * 100.0 / (SELECT COUNT(*) FROM SCHEMA("UnfurlService/Scrapers", Factor) WHERE MetricName = 'QualityFactor')) as Percentage
FROM SCHEMA("UnfurlService/Scrapers", Factor)
WHERE MetricName = 'QualityFactor'
GROUP BY Factor
ORDER BY Frequency DESC
```

### 6. Which Scraper Wins Most Often
```
SELECT Scraper, COUNT(*) as WinCount,
       (COUNT(*) * 100.0 / (SELECT COUNT(*) FROM SCHEMA("UnfurlService/Scrapers", Scraper) WHERE MetricName = 'BestQualityScraper')) as WinPercentage
FROM SCHEMA("UnfurlService/Scrapers", Scraper)
WHERE MetricName = 'BestQualityScraper'
GROUP BY Scraper
ORDER BY WinCount DESC
```

## 🚨 Alerts to Set Up

### High Failure Rate Alert
```
Metric: ScraperFailure
Statistic: Sum
Period: 5 minutes
Threshold: > 10 failures in 5 minutes
Condition: Total failures across all scrapers
```

### All Scrapers Failing Alert
```
Metric: AllScrapersFailed
Statistic: Sum
Period: 5 minutes
Threshold: > 3 in 5 minutes
Condition: Critical - no unfurls working
```

### Slow Response Time Alert
```
Metric: ScrapingTime
Statistic: Average
Period: 5 minutes
Threshold: > 30000 milliseconds (30 seconds)
Condition: Total scraping time too slow
```

### Quality Score Drop Alert
```
Metric: QualityScore
Statistic: Average
Period: 15 minutes
Threshold: < 50 average quality score
Condition: Quality degradation detected
```

## 📈 Dashboard Widget Examples

### Success Rate Gauge
- Widget Type: Number
- Metric: `ScraperSuccess` and `ScraperFailure`
- Calculation: Success / (Success + Failure) * 100
- Display as percentage

### Response Time Line Chart
- Widget Type: Line
- Metrics: `ScraperResponseTime` for each scraper
- Period: 5 minutes
- Statistic: Average

### Quality Score Histogram
- Widget Type: Bar
- Metric: `QualityScore`
- Group by: Scraper
- Statistic: Average

### Content Type Pie Chart
- Widget Type: Pie
- Metric: `ContentType`
- Group by: Type
- Show percentage distribution

## 🔧 CLI Commands for Quick Checks

### Get last 24h success rates:
```bash
aws logs insights start-query \
  --log-group-name /aws/lambda/unfurl-service \
  --start-time $(date -d '24 hours ago' +%s) \
  --end-time $(date +%s) \
  --query-string 'filter @message like /✅.*playwright|✅.*http/ | stats count() by @message'
```

### Check recent quality scores:
```bash
aws logs insights start-query \
  --log-group-name /aws/lambda/unfurl-service \
  --start-time $(date -d '1 hour ago' +%s) \
  --end-time $(date +%s) \
  --query-string 'filter @message like /📊.*quality score/ | sort @timestamp desc | limit 20'
```

This comprehensive metrics system will give you detailed insights into:
- Which scrapers succeed most often
- Average quality scores by scraper
- Response time performance
- Content type distributions
- Quality factor analysis
