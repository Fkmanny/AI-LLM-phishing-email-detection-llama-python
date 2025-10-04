from fastapi import FastAPI, Body
import subprocess
import re
import json
from urllib.parse import urlparse

app = FastAPI(title="URL Analysis Agent")

def extract_urls_from_text(text: str) -> list:
    """Extract all URLs from the email text using regex."""
    url_pattern = r'https?://[^\s<>"]+|www\.[^\s<>"]+'
    return re.findall(url_pattern, text)

def is_suspicious_url(url: str) -> bool:
    """
    Basic URL analysis for common phishing indicators.
    In the next Project version we can integrate with VirusTotal API here.
    """
    parsed = urlparse(url)
    
    # This checks for IP address 
    if re.match(r'\d+\.\d+\.\d+\.\d+', parsed.netloc):
        return True
        
    # This checks for suspicious domains (basic check for common phishing keywords)
    suspicious_keywords = ['login', 'verify', 'secure', 'account', 'update', 'confirm']
    if any(keyword in parsed.netloc.lower() for keyword in suspicious_keywords):
        return True
        
    # This checks for URL shorteners
    shorteners = ['bit.ly', 'tinyurl.com', 'goo.gl', 't.co', 'ow.ly']
    if any(shortener in parsed.netloc for shortener in shorteners):
        return True
        
    return False

@app.post("/analyze")
def analyze_urls(email_text: str = Body(..., embed=True)):
    """
    Analyzes URLs found in email for phishing indicators.
    
    Args:
        email_text: The email content to scan for URLs
        
    Returns:
        JSON with URL analysis and risk assessment
    """
    # Extract URLs from email
    urls = extract_urls_from_text(email_text)
    
    if not urls:
        return {
            "agent": "url_analysis",
            "status": "success",
            "urls_found": 0,
            "analysis": {"risk_score": 0, "verdict": "safe", "reasons": ["No URLs found"]}
        }
    
    # This analyzes each URL
    url_analysis = []
    for url in urls:
        basic_analysis = {
            "url": url,
            "suspicious": is_suspicious_url(url),
            "domain": urlparse(url).netloc
        }
        url_analysis.append(basic_analysis)
    
    # This Calculates overall risk score
    suspicious_count = sum(1 for url in url_analysis if url["suspicious"])
    risk_score = min(100, (suspicious_count / len(url_analysis)) * 100) if url_analysis else 0
    
    verdict = "malicious" if risk_score > 70 else "suspicious" if risk_score > 30 else "safe"
    
    return {
        "agent": "url_analysis",
        "status": "success",
        "urls_found": len(urls),
        "analysis": {
            "risk_score": risk_score,
            "verdict": verdict,
            "suspicious_urls": suspicious_count,
            "url_details": url_analysis,
            "reasons": [f"Found {suspicious_count} suspicious URLs out of {len(urls)} total"]
        }
    }

if __name__ == "__main__":
    import uvicorn
    # Run on port 8002 for URL analysis
    uvicorn.run(app, host="0.0.0.0", port=8002)
