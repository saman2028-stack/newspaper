import os
import time
import json
import requests
import feedparser
from bs4 import BeautifulSoup
from google import genai
from google.genai import types
from datetime import datetime

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELE_BOT_TOKEN = os.environ.get("TELE_BOT_TOKEN")
TELE_CHAT_ID = os.environ.get("TELE_CHAT_ID")

client = genai.Client(api_key=GEMINI_API_KEY)
MODEL_ID = 'gemini-3.8-flash' 

def send_to_telegram(message):
    tele_url = f"https://api.telegram.org/bot{TELE_BOT_TOKEN}/sendMessage"
    
    for i in range(0, len(message), 4000):
        chunk = message[i:i+4000]
        payload = {
            "chat_id": TELE_CHAT_ID,
            "text": chunk,
            "parse_mode": "HTML" 
        }
        
        response = requests.post(tele_url, json=payload)
        if response.status_code != 200:
            print("HTML পার্সিং এরর, সাধারণ টেক্সট হিসেবে পাঠানো হচ্ছে...")
            payload["parse_mode"] = "" 
            requests.post(tele_url, json=payload)

print("প্রথম আলোর আরএসএস থেকে তাজা খবর সংগ্রহ করা হচ্ছে...")
rss_url = "https://www.prothomalo.com/feed"
feed = feedparser.parse(rss_url)

latest_30_news = feed.entries[:30]
titles_list = ""
for i, entry in enumerate(latest_30_news):
    titles_list += f"[{i}] শিরোনাম: {entry.title}\n"

print("জেমিনি শিরোনামগুলো থেকে বিসিএস-এর জন্য সবচেয়ে গুরুত্বপূর্ণ খবর বাছাই করছে...")
screening_prompt = f"""
You are a BCS Analyst. Below are 30 recent news titles from a Bengali newspaper.
Select a maximum of 5 MOST IMPORTANT news titles strictly relevant to the Bangladesh Civil Service (BCS) exam (Economics, Constitution, Foreign Policy, Geopolitics, Environment, Core National Issues).
Ignore daily crimes, sports (unless major international achievements), entertainment, and partisan politics.
Return ONLY a JSON array of the index numbers of the selected news. Example: [3, 7, 12, 18]
If none are important, return an empty array: []

Titles:
{titles_list}
"""

max_retries = 3
selected_indices = []

for attempt in range(max_retries):
    try:
        screening_response = client.models.generate_content(
            model=MODEL_ID,
            contents=screening_prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            )
        )
        selected_indices = json.loads(screening_response.text)
        print("শিরোনাম বাছাই সফল হয়েছে।")
        break 
    except Exception as e:
        print(f"চেষ্টা {attempt + 1} ব্যর্থ: {e}")
        if attempt < max_retries - 1:
            print("সার্ভার ব্যস্ত, ২০ সেকেন্ড পর আবার চেষ্টা করা হচ্ছে...")
            time.sleep(20)
        else:
            print("সার্ভার অতিরিক্ত ব্যস্ত। আজকের মতো স্ক্রিনিং বাতিল করা হলো।")

print(f"বাছাই করা খবরের ইনডেক্স: {selected_indices}")
today_date = datetime.now().strftime("%Y-%m-%d")

count = 0
for index in selected_indices:
    if index >= len(latest_30_news):
        continue
        
    entry = latest_30_news[index]
    title = entry.title
    link = entry.link
    
    print(f"প্রসেস করা হচ্ছে: {title}")
    
    article_processed = False
    summary = ""
    
    for attempt in range(max_retries):
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
            response = requests.get(link, headers=headers, timeout=10) 
            soup = BeautifulSoup(response.content, 'html.parser')
            paragraphs = soup.find_all('p')
            full_article = " ".join([p.text for p in paragraphs])
            
            prompt = f"""
System Role:
You are an expert 'BCS Analyst AI'. Analyze the Bengali newspaper article and extract specific information strictly aligned with the BCS syllabus.
[Current System Date: {today_date}]

Strict Constraints & Rules:
1. STRICT GROUNDING: Extract ONLY from the provided text.
2. NEUTRAL TONE & SOURCE FILTERING: Ignore partisan rhetoric.
3. ABSOLUTELY NO MARKDOWN: You MUST NOT use asterisks (**) for bolding or hashes (###). Use ONLY standard HTML tags like <b>text</b> for bold text. Use <br> for line breaks.

Execution Logic - Phase 1: Evaluation
Categorize and output exactly ONE of these status lines first:
* Status: Irrelevant. [Reasoning] (If it is political rhetoric or lacks BCS depth)
* Status: Prelim-Only. [Reasoning] (If only facts/treaties exist)
* Status: Written-Focused. [Reasoning] (If structural/policy analysis exists)

Execution Logic - Phase 2: Outputs (If not Irrelevant)
Generate Anki Flashcards in exact format: Question ; Answer ; Tags (Use ONLY semicolons as delimiter).
Deduce exact years for temporal terms like "recent" based on System Date and add bracketed proofs.

If Written-Focused, generate bullet points under:
১. প্রাসঙ্গিক তথ্য ও পরিসংখ্যান:
২. মূল সমস্যা বা সংকটের কারণ:
৩. নীতিগত সুপারিশ বা সমাধান:
(If data missing, write "প্রবন্ধে উল্লেখ নেই")

খবরের শিরোনাম: {title}
বিস্তারিত: {full_article}
"""
            
            final_response = client.models.generate_content(
                model=MODEL_ID,
                contents=prompt
            )
            summary = final_response.text
            article_processed = True
            break 
            
        except Exception as e:
            print(f"এই খবরটি প্রসেস করতে ত্রুটি দেখা দিয়েছে (চেষ্টা {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                time.sleep(20)
            else:
                print("খবরটি স্কিপ করা হলো।")
                
    if article_processed and summary:
        if "Status: Irrelevant." not in summary:
            # মার্কডাউন স্যানিটাইজেশন নিশ্চিত করা
            summary = summary.replace("**", "").replace("###", "").replace("`", "")
            message = f"📚 <b>BCS Analyst AI আপডেট</b>\n\n{summary}\n\n🔗 <a href='{link}'>বিস্তারিত খবর</a>"
            send_to_telegram(message)
            print("টেলিগ্রামে পাঠানো হয়েছে।")
        else:
            print("খবরটি পরীক্ষার জন্য উপযোগী নয় (Condition A), বাদ দেওয়া হলো।")
            
    time.sleep(10)
    count += 1

print("আজকের মতো নিউজ প্রসেসিং শেষ!")
