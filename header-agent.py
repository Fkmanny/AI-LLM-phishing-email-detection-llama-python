from fastapi import FastAPI, Body
import re
import json

app = FastAPI(title="Header Analysis Agent")

def parse_email_headers(email_text: str) -> dict:
    """
    Extract and parse email headers from raw email text.
    
    Args:
        email_text: Raw email content with headers
        
    Returns:
        Dictionary of parsed header fields
    """
    headers = {}
    
    # Common email header patterns
    patterns = {
        "from": r"From:\s*(.+)",
        "to": r"To:\s*(.+)",
        "subject": r"Subject:\s*(.+)",
        "date": r"Date:\s*(.+)",
        "return_path": r"Return-Path:\s*<(.+)>",
        "received": r"Received:\s*(.+)",
        "message_id": r"Message-ID:\s*(.+)",
        "content_type": r"Content-Type:\s*(.+)"
    }
    
    for field, pattern in patterns.items():
        match = re.search(pattern, email_text, re.IGNORECASE)
        if match:
            headers[field] = match.group(1).strip()
    
    return headers

def analyze_headers(headers: dict) -> dict:
    """
    Analyze email headers for signs of spoofing or manipulation.
    
    Args:
        headers: Dictionary of email headers
        
    Returns:
        Analysis results with risk indicators
    """
    risk_factors = []
    risk_score = 0
    
    # Check 1: From vs Return-Path mismatch
    if 'from' in headers and 'return_path' in headers:
        from_domain = re.search(r'@([\w.-]+)', headers['from'])
        return_domain = re.search(r'@([\w.-]+)', headers['return_path'])
        
        if from_domain and return_domain and from_domain.group(1) != return_domain.group(1):
            risk_factors.append("From and Return-Path domains don't match")
            risk_score += 30
    
    # Check 2: Suspicious subject lines
    if 'subject' in headers:
        subject = headers['subject'].lower()
        urgent_keywords = ['urgent', 'immediate', 'action required', 'verify', 'security alert']
        if any(keyword in subject for keyword in urgent_keywords):
            risk_factors.append("Subject contains urgent/action-oriented language")
            risk_score += 20
    
    # Check 3: Missing important headers
    important_headers = ['from', 'to', 'subject', 'date']
    missing_headers = [h for h in important_headers if h not in headers]
    if missing_headers:
        risk_factors.append(f"Missing important headers: {', '.join(missing_headers)}")
        risk_score += len(missing_headers) * 10
    
    # Check 4: Multiple Received headers (potential relay abuse)
    if 'received' in headers:
        received_count = len(re.findall(r'Received:', headers.get('received', '')))
        if received_count > 3:
            risk_factors.append(f"Multiple ({received_count}) Received headers detected")
            risk_score += 15
    
    return {
        "risk_score": min(100, risk_score),
        "verdict": "malicious" if risk_score > 70 else "suspicious" if risk_score > 30 else "safe",
        "risk_factors": risk_factors,
        "headers_analyzed": list(headers.keys())
    }

@app.post("/analyze")
def analyze_email_headers(email_text: str = Body(..., embed=True)):
    """
    Analyzes email headers for signs of spoofing and manipulation.
    
    Args:
        email_text: Raw email content including headers
        
    Returns:
        JSON with header analysis and risk assessment
    """
    try:
        # Parse headers from email text
        headers = parse_email_headers(email_text)
        
        if not headers:
            return {
                "agent": "header_analysis",
                "status": "error",
                "error": "No recognizable email headers found"
            }
        
        # Analyze the headers for risks
        analysis_result = analyze_headers(headers)
        analysis_result["headers_found"] = headers
        
        return {
            "agent": "header_analysis",
            "status": "success",
            "analysis": analysis_result
        }
        
    except Exception as e:
        return {
            "agent": "header_analysis",
            "status": "error",
            "error": str(e)
        }

if __name__ == "__main__":
    import uvicorn
    # Run on port 8003 for header analysis
    uvicorn.run(app, host="0.0.0.0", port=8003)
