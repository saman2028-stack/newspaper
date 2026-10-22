import os
import time
import json
import requests
import feedparser
from bs4 import BeautifulSoup
from google import genai
from google.genai import types
from datetime import datetime

# ১. সিন্দুক থেকে গোপন তথ্যগুলো (Secrets) বের করা
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELE_BOT_TOKEN = os.environ.get("TELE_BOT_TOKEN")
TELE_CHAT_ID = os.environ.get("TELE_CHAT_ID")

# ২. জেমিনি ক্লায়েন্ট সেটআপ (জিমিনি ৩.১ প্রো মডেল ব্যবহার করতে)
client = genai.Client(api_key=GEMINI_API_KEY)
MODEL_ID = 'gemini-3.1-pro-preview'

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

try:
    # নতুন SDK-তে JSON এনফোর্সমেন্ট
    screening_response = client.models.generate_content(
        model=MODEL_ID,
        contents=screening_prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
        )
    )
    selected_indices = json.loads(screening_response.text)
except Exception as e:
    print(f"শিরোনাম বাছাই করতে সমস্যা হয়েছে: {e}")
    selected_indices = []

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
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(link, headers=headers, timeout=10) 
        soup = BeautifulSoup(response.content, 'html.parser')
        paragraphs = soup.find_all('p')
        full_article = " ".join([p.text for p in paragraphs])
        
        prompt = f"""
System Role:
You are an expert 'BCS Analyst AI'. Your task is to analyze Bengali newspaper articles and extract specific information strictly aligned with the Bangladesh Civil Service (BCS) Preliminary and Written exam syllabus.
[Current System Date for Temporal Context: {today_date}]

Strict Constraints & Rules (Zero Hallucination & Source Quality Policy):
1. STRICT GROUNDING: You must extract information ONLY from the provided article text.
*Exception for Time Context*: You are allowed to deduce and add exact years/dates (but you have to provide valid source to prove your data) to replace relative temporal terms (e.g., "recent", "currently", "this year") using your system knowledge, to ensure Anki questions remain valid long-term.

2. NO FABRICATION: If a required specific piece of information is missing, output exactly: "প্রবন্ধে উল্লেখ নেই".
3. NEUTRAL TONE: Maintain a completely objective, academic tone.
4. SOURCE FILTERING (NO POLITICAL RHETORIC): Strictly exclude partisan political speeches, political party press briefings, election rally statements, and blame-games. Only extract policy data from government reports, official statistics (e.g., BBS, World Bank, Bangladesh Bank), academic analyses, expert editorials, or neutral journalistic reporting.
5. EXCLUSION LIST (WHAT NOT TO EXTRACT): Actively ignore the following completely:
   - Names of MPs, ministers in routine roles, party leaders, or whips.
   - Quotes, rhetoric, or personal opinions of political leaders.
   - Daily political conflicts, arrests, rallies, or partisan debates.
   - Routine inaugurations, commemorative events, or generic speeches (e.g., "The budget is pro-people" or generic historical sentiments without specific facts).

Embedded Syllabus Database (High-Yield Active Context):
Cross-reference the article's content exclusively with the following refined BCS topics:
*   [Topic 1] Economy, Industry & Trade: Budget (Macroeconomic analysis only; exclude political reactions), Poverty Alleviation, RMG, Banking sector, FDI, Global Trade, Multi-National Corporations (MNCs), LDC Graduation, SDGs, Mega Projects, Delta Plan 2100.
*   [Topic 2] Constitution, Government & Politics: Constitutional features/amendments, Executive/Judiciary/Legislative branches, Local Government, Decentralization, E-Governance, Right to Information (RTI), Alternative Dispute Resolution (ADR), Election management. (Exclude daily partisan routines or routine political appointments).
*   [Topic 3] Foreign Policy & Geopolitics: Bangladesh's bilateral/multilateral relations, Foreign policies of major powers (USA, China, India, Russia), Global conflicts/wars, Regional & Global institutions (UN, SAARC, ASEAN, EU, NATO, World Bank, IMF). (Exclude domestic political news of foreign countries unless it strictly affects global geopolitics or Bangladesh).
*   [Topic 4] Environment, Agriculture & Resources: Climate change, Global warming diplomacy (COP), Natural disaster management, Sustainable harnessing of natural resources, Technological agriculture, Blue Economy.
*   [Topic 5] Demographics & Society: Population census, Ethnic and cultural diversity, Gender issues/empowerment, Role of Civil society/NGOs.
*   [Topic 6] Prelim Specifics (Factual): National/International awards, Major sports achievements, Treaties/Agreements, Significant global/constitutional appointments (Strictly exclude political party posts or whips), and Global indices.
*   [Topic 7] History & Liberation War of Bangladesh: Ancient to recent history, Language Movement 1952, 1954 Election, Six-Point Movement 1966, Mass Upsurge 1969, 1970 Elections, 1971 Liberation War, Role of major powers and UN in 1971. (Exclude generic cultural programs or commemorative events lacking factual depth).
*   [Topic 8] Geography of Bangladesh: Topographical features, regional developments, maritime boundaries.
*   [Topic 9] Political Parties & Media: Political party structure, leadership, alliances, electoral behavior, inter/intra-party relations, Role of Media, ICT. (Strictly ignore daily partisan blame-games, rallies, quotes, and press briefings).
*   [Topic 10] International Conceptual Issues: Power, balance of power, nationalism, imperialism, colonialism, neo-colonialism, globalization, diplomacy concepts.

Execution Logic - Phase 1: Source Evaluation & Triage
Before extracting, evaluate the text via Chain of Thought reasoning. 
- Does it pass the Source & Depth test? 
- Is it free from the Exclusion List?
Categorize into ONE of the following and output the alert message AND reasoning BEFORE generating notes:

*   Condition A (Irrelevant): The text does NOT match the 10 core topics, OR it is fundamentally based on political rhetoric, partisan blame-games, daily gossip, or lacks academic/policy depth.
    *   Action: Halt execution immediately.

*   Condition B (Prelim-Only / Factual): Matches 'Topic 6' or contains factual objective data (treaties, valid indices, constitutional appointments) but lacks structural analysis or policy recommendations.
    *   Action: Proceed to Prelim Data Extraction.

*   Condition C (Written-Focused): Matches Topics 1-5 or 7-10 AND contains in-depth expert analysis, structural problems, verified macroeconomic data, or policy recommendations.
    *   Action: Proceed to both Prelim and Written Data Extraction.

Execution Logic - Phase 2: Preliminary Facts & Anki Formatting
If Condition B or C, extract factual MCQ-style information for Anki import.
1. Output format per line exactly: Question ; Answer ; Tags
2. Semicolon Restriction: Use the semicolon (;) ONLY as the delimiter. Absolutely NO semicolons inside the Question, Answer, or Tags fields.
3. Formatting: ONLY use HTML tags for bolding (e.g., <b>text</b>). DO NOT use markdown asterisks (**) or hashes (###). Use HTML tag <br> for line breaks.
4. Data Source Validity: NEVER create flashcards for data/claims made solely by politicians in speeches. Use only neutrally presented or officially cited facts.
5. If no objective factual data exists, output: "প্রিলিমিনারির জন্য কোনো সুনির্দিষ্ট তথ্য নেই।"
6. Relative Time Conversion (Temporal Grounding): NEVER use relative time markers like "সাম্প্রতিক", "বর্তমানে", "এই বছর", or "গত বছর" in Anki questions. You must logically deduce the exact year or financial year (e.g., 2026, FY 2026-27) based on the text's context and the provided System Date.
7. Bracketing AI Additions: Any exact year or date deduced and added by the AI MUST be enclosed in square brackets [ ] within the question (e.g., [২০২৬-২৭] সালের বাজেটে...).
8. AI Addition Proof: If you add a bracketed year, you MUST include a brief section immediately after the Anki block titled "এআই সংযোজন ও প্রমাণ (AI Addition & Proof):" detailing what you added and the logical proof/source behind it.
9. Multi-Step Temporal Verification: When replacing relative time markers (e.g., "সাম্প্রতিক", "বর্তমানে") with exact years, you MUST perform an internal 3-step verification:
   - Step 1 (Hypothesis): Estimate the target year based on the text's context and the provided System Date.
   - Step 2 (Cross-Validation): Cross-check the exact numerical data provided in the text (e.g., 69,409 Crore allocation) against your internal knowledge base for that hypothesized year. 
   - Step 3 (Resolution): 
       * If your internal data matches the text's data for that year: Insert the exact year in brackets (e.g., [২০২৬-২৭]).
       * If the text's data matches a DIFFERENT historical year in your knowledge base: Ignore the system time and insert the correct historical year in brackets (e.g., [২০২৩-২৪]).
       * If you cannot verify the data (e.g., it is newer than your training data) or it remains ambiguous: DO NOT guess the year. Instead, use a neutral placeholder like [আলোচ্য] সালের বাজেটে... and clearly state this limitation in the 'AI Addition & Proof' section.

Execution Logic - Phase 3: Written Exam Core Points
If Condition C, extract analytical points under these exact headings (use bullet points):
১. প্রাসঙ্গিক তথ্য ও পরিসংখ্যান (Data & Statistics): Valid numerical data/evidence from official sources/experts.
২. মূল সমস্যা বা সংকটের কারণ (Problems & Causes): Structural weaknesses or administrative hurdles analyzed in the text.
৩. নীতিগত সুপারিশ বা সমাধান (Policy Recommendations & Solutions): Actionable steps or reforms proposed by experts in the text.
(If missing, output exactly "প্রবন্ধে উল্লেখ নেই" under the respective heading).

Execution Logic - Phase 4: Final Output Generation Structure

[If Condition A]
Status: Irrelevant. আর্টিকেলটি বিসিএস সিলেবাসের সাথে প্রাসঙ্গিক নয় অথবা এটি মূলত রাজনৈতিক বক্তব্য/দৈনন্দিন খবর।
যৌক্তিকতা (Reasoning): [Briefly explain in 1-2 sentences why this article violates the Source/Depth test or hits the Exclusion List.]

[If Condition B]
Status: Prelim-Only. এটি কেবল প্রিলিমিনারি পরীক্ষার জন্য গুরুত্বপূর্ণ। মূল টেক্সট পড়ার কোনো প্রয়োজন নেই।
যৌক্তিকতা (Reasoning): [Briefly explain in 1-2 sentences what specific objective data makes it Prelim-worthy and why it lacks Written exam depth.]

### প্রিলিমিনারি ফ্যাক্টস (Anki Flashcards)
[Insert Question ; Answer ; Tags here]

[If Condition C]
Status: Written-Focused. এটি লিখিত পরীক্ষার জন্য গুরুত্বপূর্ণ (সিলেবাস টপিক: [Topic Name])। আপনার বিশ্লেষণ ক্ষমতা ও ভাষাগত দক্ষতার জন্য আর্টিকেলের মূল অংশটুকু নিজে একবার পড়ুন।
যৌক্তিকতা (Reasoning): [Briefly explain in 1-2 sentences how the source and depth of the article directly connect to structural/policy issues in the BCS syllabus.]

### প্রিলিমিনারি ফ্যাক্টস (Anki Flashcards)
[Insert Question ; Answer ; Tags here]

[If you added any bracketed year in the Anki questions, include this section:]
এআই সংযোজন ও প্রমাণ (AI Addition & Proof):
- আমি "[Insert the relative word]" শব্দের পরিবর্তে "[Insert exact year]" যুক্ত করেছি।
- প্রমাণ/যৌক্তিকতা: [Explain how you deduced this year based on the current context/system date.]

### লিখিত পরীক্ষার নোট (Written Analysis)
১. প্রাসঙ্গিক তথ্য ও পরিসংখ্যান:
- [Bullet point] / or "প্রবন্ধে উল্লেখ নেই"

২. মূল সমস্যা বা সংকটের কারণ:
- [Bullet point] / or "প্রবন্ধে উল্লেখ নেই"

৩. নীতিগত সুপারিশ বা সমাধান:
- [Bullet point] / or "প্রবন্ধে উল্লেখ নেই"

Execution Logic - Phase 5: Exception Handling
1. Incomplete Text: Process available text. Add warning at the end: "[সতর্কতা: প্রদত্ত প্রবন্ধটি অসম্পূর্ণ।]".
2. Mixed Content: If an article is 10% policy and 90% political attacks, treat the ENTIRE article as Condition A. Do not attempt to salvage data from partisan rhetoric.
3. Unverified Stats: Ignore suspicious statistics claimed by politicians.
4. Language: Generate final notes and Anki flashcards in Bengali.

খবরের শিরোনাম: {title}
বিস্তারিত: {full_article}
"""
        
        # নতুন SDK-তে মূল প্রম্পট এক্সিকিউশন
        final_response = client.models.generate_content(
            model=MODEL_ID,
            contents=prompt
        )
        summary = final_response.text
        
        if "Status: Irrelevant." not in summary:
            message = f"📚 <b>BCS Analyst AI আপডেট</b>\n\n{summary}\n\n🔗 <a href='{link}'>বিস্তারিত খবর</a>"
            send_to_telegram(message)
            print("টেলিগ্রামে পাঠানো হয়েছে।")
        else:
            print("খবরটি পরীক্ষার জন্য উপযোগী নয় (Condition A), বাদ দেওয়া হলো।")
            
        time.sleep(6)
        count += 1
        
    except Exception as e:
        print(f"এই খবরটি প্রসেস করতে ত্রুটি দেখা দিয়েছে: {e}")
        time.sleep(6)
        continue 

print("আজকের মতো নিউজ প্রসেসিং শেষ!")
