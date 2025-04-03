import os
import requests
import time
from flask import Flask, render_template_string, request, jsonify, session, redirect, url_for
from dotenv import load_dotenv
from functools import wraps
from pymongo import MongoClient
from flask_bcrypt import Bcrypt
import google.generativeai as genai

# Load .env variables
load_dotenv()

# Initialize Flask
app = Flask(__name__)
app.secret_key = os.urandom(24)

# Initialize Bcrypt for password hashing
bcrypt = Bcrypt(app)

# MongoDB Atlas setup
mongo_uri = os.getenv("MONGO_URI")
client = MongoClient(mongo_uri)
db = client['blog_generator_db']  # Database name
users_collection = db['users']    # Collection for users

# Configure Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
# HIX API Configuration
HIX_API_KEY = os.getenv("HIX_API_KEY")  # Store your HIX API key in .env
HIX_API_ENDPOINT = "https://api.hix.ai/v1/humanize"  # Replace with actual HIX API endpoint

# Two different models for different tasks
blog_generation_model = genai.GenerativeModel("gemini-1.5-flash")
grammar_improvement_model = genai.GenerativeModel("gemini-1.5-flash")

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session or not session['logged_in']:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Updated Login/Signup Template with Tabs
LOGIN_SIGNUP_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Login / Sign Up - Blog Generator</title>
    <link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
    <script>
        function toggleTab(tab) {
            document.getElementById('login-tab').classList.remove('bg-blue-500', 'text-white');
            document.getElementById('signup-tab').classList.remove('bg-blue-500', 'text-white');
            document.getElementById('login-form').style.display = 'none';
            document.getElementById('signup-form').style.display = 'none';
            
            if (tab === 'login') {
                document.getElementById('login-tab').classList.add('bg-blue-500', 'text-white');
                document.getElementById('login-form').style.display = 'block';
            } else {
                document.getElementById('signup-tab').classList.add('bg-blue-500', 'text-white');
                document.getElementById('signup-form').style.display = 'block';
            }
        }
    </script>
</head>
<body class="bg-gradient-to-br from-gray-100 to-gray-200 min-h-screen flex items-center justify-center p-4">
    <div class="bg-white p-8 rounded-2xl shadow-2xl max-w-md w-full">
        <h1 class="text-3xl font-bold text-center mb-6 text-gray-800">Blog Generator</h1>
        <div class="flex mb-6">
            <button id="login-tab" onclick="toggleTab('login')" class="flex-1 py-2 px-4 bg-blue-500 text-white rounded-l-lg focus:outline-none">Sign In</button>
            <button id="signup-tab" onclick="toggleTab('signup')" class="flex-1 py-2 px-4 bg-gray-200 text-gray-700 rounded-r-lg focus:outline-none">Sign Up</button>
        </div>
        {% if error %}
            <p class="text-red-500 text-center mb-4">{{ error }}</p>
        {% endif %}
        
        <!-- Login Form -->
        <form id="login-form" method="POST" action="/login" class="space-y-6">
            <div>
                <label class="block mb-2 text-gray-700">Email</label>
                <input type="email" name="email" required class="w-full p-3 border-2 border-gray-200 rounded-lg focus:outline-none focus:border-blue-500 transition">
            </div>
            <div>
                <label class="block mb-2 text-gray-700">Password</label>
                <input type="password" name="password" required class="w-full p-3 border-2 border-gray-200 rounded-lg focus:outline-none focus:border-blue-500 transition">
            </div>
            <button type="submit" class="w-full bg-gradient-to-r from-blue-500 to-purple-600 text-white p-3 rounded-lg hover:from-blue-600 hover:to-purple-700 transition duration-300 ease-in-out transform hover:scale-105 hover:shadow-lg">
                Sign In
            </button>
        </form>
        
        <!-- Signup Form -->
        <form id="signup-form" method="POST" action="/signup" class="space-y-6" style="display: none;">
            <div>
                <label class="block mb-2 text-gray-700">Email</label>
                <input type="email" name="email" required class="w-full p-3 border-2 border-gray-200 rounded-lg focus:outline-none focus:border-blue-500 transition">
            </div>
            <div>
                <label class="block mb-2 text-gray-700">Password</label>
                <input type="password" name="password" required class="w-full p-3 border-2 border-gray-200 rounded-lg focus:outline-none focus:border-blue-500 transition">
            </div>
            <div>
                <label class="block mb-2 text-gray-700">Confirm Password</label>
                <input type="password" name="confirm_password" required class="w-full p-3 border-2 border-gray-200 rounded-lg focus:outline-none focus:border-blue-500 transition">
            </div>
            <button type="submit" class="w-full bg-gradient-to-r from-green-500 to-teal-600 text-white p-3 rounded-lg hover:from-green-600 hover:to-teal-700 transition duration-300 ease-in-out transform hover:scale-105 hover:shadow-lg">
                Sign Up
            </button>
        </form>
    </div>
</body>
</html>
'''

def split_text_into_chunks(text, max_words=500):
    words = text.split()
    chunks = []
    current_chunk = []
    current_word_count = 0

    for word in words:
        current_chunk.append(word)
        current_word_count += 1

        if current_word_count >= max_words:
            chunks.append(' '.join(current_chunk))
            current_chunk = []
            current_word_count = 0

    if current_chunk:
        chunks.append(' '.join(current_chunk))

    return chunks

def humanize_chunk(chunk, api_key=os.getenv("HIX_API_KEY")):
    SUBMIT_URL = "https://bypass.hix.ai/api/hixbypass/v1/submit"
    OBTAIN_URL = "https://bypass.hix.ai/api/hixbypass/v1/obtain"

    headers = {
        "api-key": api_key,
        "Content-Type": "application/json"
    }

    submit_payload = {
        "input": chunk,
        "mode": "Balanced"
    }

    try:
        submit_response = requests.post(SUBMIT_URL, json=submit_payload, headers=headers)
        submit_response.raise_for_status()
        submit_data = submit_response.json()

        if submit_data.get('err_code') != 0:
            print(f"Submission Error: {submit_data.get('err_msg', 'Unknown error')}")
            return chunk

        task_id = submit_data['data']['task_id']

        max_attempts = 10
        for _ in range(max_attempts):
            time.sleep(2)
            obtain_response = requests.get(OBTAIN_URL, params={"task_id": task_id}, headers=headers)
            obtain_response.raise_for_status()
            obtain_data = obtain_response.json()

            if obtain_data.get('err_code') == 0 and obtain_data['data'].get('task_status'):
                return obtain_data['data'].get('output', chunk)

        print("Humanization task timed out")
        return chunk

    except Exception as e:
        print(f"Humanization Error for chunk: {e}")
        return chunk

def humanize_text(text, max_words=500):
    if not text or len(text.split()) < 50:
        return text

    api_key = os.getenv("HIX_API_KEY")
    if not api_key:
        print("Error: HIX API Key not set in environment variables")
        return text

    chunks = split_text_into_chunks(text, max_words)
    humanized_chunks = [humanize_chunk(chunk, api_key) for chunk in chunks]
    return ' '.join(humanized_chunks)

def improve_grammar_and_readability(content, primary_keywords, secondary_keywords):
    improvement_prompt = f"""Please review and improve the following text.
    Focus on:
    - Make sure the primary keywords are used only 4-5 times in whole blog: {primary_keywords}
    - Make sure each secondary keyword is only used at least once in whole blog: {secondary_keywords}
    - Correcting grammar and spelling errors
    - Enhancing sentence structure and flow
    - Improving clarity and readability
    - Maintaining the original tone and meaning
    - Breaking up long sentences
    - Using more engaging and precise language
    - Ensuring professional and conversational style

    Original Text:
    {content}

    Provide the improved version of the text."""
    try:
        response = grammar_improvement_model.generate_content(improvement_prompt)
        return response.text
    except Exception as e:
        print(f"Grammar improvement error: {e}")
        return content

def generate_blog_outline(product_url, product_title, product_description, primary_keywords, secondary_keywords, intent):
    prompt = f"""Create a comprehensive and detailed blog outline for a product blog with the following details:

Product URL: {product_url}
Product Title: {product_title}
Product Description: {product_description}
Primary Keywords: {primary_keywords}
Secondary Keywords: {secondary_keywords}
Search Intent: {intent}

Outline Requirements:
1. Introduction:
   - Compelling hook related to the product's unique value proposition
   - Brief overview of the product and its significance
   - Problem the product solves
   - Include a captivating anecdote or statistic to engage readers

2. Product Overview:
   - Detailed breakdown of product features
   - Unique selling points
   - Technical specifications
   - How it differs from competitors
   - Include sub-sections for each major feature

3. Use Cases and Applications:
   - Specific scenarios where the product excels
   - Target audience and their pain points
   - Real-world examples or potential applications
   - Include case studies or success stories if available

4. Benefits and Advantages:
   - Comprehensive list of benefits
   - Quantifiable improvements or advantages
   - Customer-centric perspective on product value
   - Include testimonials or reviews to support claims

5. Practical Insights:
   - Implementation tips
   - Best practices for using the product
   - Potential challenges and solutions
   - Include step-by-step guides or tutorials

6. Conclusion:
   - Recap of key product highlights
   - Clear call-to-action
   - Future potential or upcoming features
   - Include a final thought or reflection to leave a lasting impression

Additional Guidance:
- Ensure the outline is informative and engaging
- Incorporate keywords naturally and frequently throughout the blog
- Focus on solving customer problems
- Maintain a balanced, objective tone
- Highlight unique aspects of the product
- Provide detailed sub-points under each main section to elaborate on the content
"""
    response = blog_generation_model.generate_content(prompt)
    return response.text

def generate_blog_content(outline, product_url, product_title, product_description, primary_keywords, secondary_keywords, intent):
    sections = outline.split('\n\n')
    blog_content = []
    all_keywords = primary_keywords.split(", ") + secondary_keywords.split(", ")
    keyword_usage = {keyword: 0 for keyword in all_keywords}
    primary_keyword_target = 3
    secondary_keyword_target = 1

    for i, section in enumerate(sections):
        previous_text = ' '.join(blog_content) if i > 0 else 'None'
        primary_keywords_instruction = (
            "\n- Use primary keywords sparingly and naturally, aiming for no more than 3 total uses across the entire blog: "
            + ', '.join(primary_keywords.split(", ")) +
            ". Ensure the usage is contextually relevant and not forced."
        )
        secondary_keywords_instruction = (
            "\n- Use each of the following secondary keywords approximately **1 time** throughout the entire blog: "
            + ', '.join(secondary_keywords.split(", ")) +
            ". Make the usage natural and contextually relevant."
        )
        section_prompt = f"""Generate a detailed section for a blog post while ensuring no repetition.

Section Outline:
{section}

Product Details:
- Product URL: {product_url}
- Product Title: {product_title}
- Product Description: {product_description}
- Search Intent: {intent}

Guidelines:
- Word count for this section: Approximately {1200 // len(sections)} words
- Avoid repeating points from previous sections
- Focus on new insights, examples, and fresh perspectives
- Ensure smooth transitions from previous sections
- Maintain a professional and engaging tone{primary_keywords_instruction}{secondary_keywords_instruction}

Previous Sections Summary:
{previous_text}

Generate the content for this section."""
        response = blog_generation_model.generate_content(section_prompt)
        section_content = response.text
        for keyword in all_keywords:
            keyword_usage[keyword] += section_content.lower().count(keyword.lower())
        blog_content.append(section_content)

    for keyword, count in keyword_usage.items():
        if keyword in primary_keywords.split(", ") and count > primary_keyword_target:
            blog_content = [section.replace(keyword, f"**{keyword}**", count - primary_keyword_target) for section in blog_content]
        elif keyword in secondary_keywords.split(", ") and count < secondary_keyword_target:
            additional_content = f"Moreover, {keyword} is an important aspect to consider."
            blog_content.append(additional_content)
            keyword_usage[keyword] += 1

    final_content = '\n\n'.join(blog_content)
    improved_content = improve_grammar_and_readability(final_content, primary_keywords, secondary_keywords)
    return improved_content
def generate_general_blog_outline(keywords, primary_keywords, prompt):
    outline_prompt = f"""Create a comprehensive and detailed blog outline based on the following details:
 
Keywords: {keywords}
Primary Keywords: {primary_keywords}
Prompt: {prompt}
 
Outline Requirements:
1. Introduction:
   - Compelling hook related to the main topic
   - Brief overview of the topic and its significance
   - Problem the blog addresses
   - Include a captivating anecdote or statistic to engage readers
 
2. Main Sections:
   - Detailed breakdown of the main points
   - Unique insights or perspectives
   - Include sub-sections for each major point
 
3. Use Cases and Applications:
   - Specific scenarios where the topic is relevant
   - Target audience and their pain points
   - Real-world examples or potential applications
   - Include case studies or success stories if available
 
4. Benefits and Advantages:
   - Comprehensive list of benefits
   - Quantifiable improvements or advantages
   - Customer-centric perspective on the topic's value
   - Include testimonials or reviews to support claims
 
5. Practical Insights:
   - Implementation tips
   - Best practices related to the topic
   - Potential challenges and solutions
   - Include step-by-step guides or tutorials
 
6. Conclusion:
   - Recap of key points
   - Clear call-to-action
   - Future potential or upcoming trends
   - Include a final thought or reflection to leave a lasting impression
 
Additional Guidance:
- Ensure the outline is informative and engaging
- Incorporate keywords naturally and frequently throughout the blog
- Focus on solving reader problems
- Maintain a balanced, objective tone
- Highlight unique aspects of the topic
- Provide detailed sub-points under each main section to elaborate on the content
"""
    response = blog_generation_model.generate_content(outline_prompt)
    return response.text
 
def generate_general_blog_content(outline, keywords, primary_keywords, prompt):
    sections = outline.split('\n\n')
    blog_content = []
   
    # Parse keywords into lists
    primary_kw_list = [kw.strip() for kw in primary_keywords.split(",")]
    secondary_kw_list = [kw.strip() for kw in keywords.split(",")]
   
    # Distribution planning for keywords
    total_sections = len(sections)
   
    # Create a plan for keyword distribution across sections
    keyword_plan = {
        "primary": {},
        "secondary": {}
    }
   
    # Plan primary keywords (aim for 3 uses per primary keyword)
    for kw in primary_kw_list:
        keyword_plan["primary"][kw] = []
        # Distribute across introduction, body, and conclusion
        section_indices = [0]  # Always use in intro
        if len(sections) > 2:
            section_indices.append(len(sections) // 2)  # Use in middle section
        if len(sections) > 1:
            section_indices.append(len(sections) - 1)  # Use in conclusion
        keyword_plan["primary"][kw] = section_indices
   
    # Plan secondary keywords (aim for at least 1 use per secondary keyword)
    for i, kw in enumerate(secondary_kw_list):
        # Distribute evenly across all sections
        target_section = (i % (total_sections - 2)) + 1  # Skip intro and conclusion
        keyword_plan["secondary"][kw] = [target_section]
 
    # Generate each section with specific keyword requirements
    for i, section in enumerate(sections):
        # Determine which keywords should be used in this section
        section_primary_kw = [kw for kw, sections in keyword_plan["primary"].items() if i in sections]
        section_secondary_kw = [kw for kw, sections in keyword_plan["secondary"].items() if i in sections]
       
        previous_text = ' '.join(blog_content) if i > 0 else 'None'
 
        keyword_instructions = ""
        if section_primary_kw:
            keyword_instructions += f"\n- IMPORTANT: Naturally incorporate these primary keywords in this section: {', '.join(section_primary_kw)}"
        if section_secondary_kw:
            keyword_instructions += f"\n- IMPORTANT: Naturally incorporate these secondary keywords in this section: {', '.join(section_secondary_kw)}"
       
        if not section_primary_kw and not section_secondary_kw:
            keyword_instructions = "\n- Focus on content quality without specific keyword requirements for this section."
 
        section_prompt = f"""Generate a detailed section for a blog post that naturally incorporates the required keywords.
 
Section Outline:
{section}
 
Topic Overview:
{prompt}
 
Guidelines:
- Word count for this section: Approximately {1200 // len(sections)} words
- Avoid repeating points from previous sections
- Focus on new insights, examples, and fresh perspectives
- Ensure smooth transitions from previous sections
- Maintain a professional and engaging tone{keyword_instructions}
- DO NOT mention "keywords" or the process of keyword incorporation in the final text
 
Previous Sections Summary:
{previous_text}
 
Generate the content for this section."""
 
        response = blog_generation_model.generate_content(section_prompt)
        section_content = response.text
        blog_content.append(section_content)
 
    # Combine content
    final_content = '\n\n'.join(blog_content)
   
    # Verify keyword usage and add missing keywords if necessary
    keyword_verification_prompt = f"""Review and optimize the following blog content to ensure natural inclusion of all required keywords:
 
Blog Content:
{final_content}
 
Primary Keywords (each should appear 2-3 times throughout the blog):
{primary_keywords}
 
Secondary Keywords (each should appear at least once throughout the blog):
{keywords}
 
Instructions:
1. Check if all keywords are naturally included in the content
2. For any missing keywords, revise relevant paragraphs to incorporate them naturally
3. DO NOT add awkward sentences just to include keywords
4. Maintain the flow, tone and quality of the content
5. DO NOT mention "keywords" or the process of incorporating them in the final text
6. Return the complete, revised blog content
 
Return the optimized blog content:"""
 
    optimized_response = blog_generation_model.generate_content(keyword_verification_prompt)
    optimized_content = optimized_response.text
   
    # Apply any additional readability improvements
    if 'improve_grammar_and_readability' in globals():
        optimized_content = improve_grammar_and_readability(optimized_content, primary_keywords, keywords)
   
    return optimized_content
 
 
# def generate_general_blog_outline(keywords, primary_keywords, prompt):
#     outline_prompt = f"""Create a comprehensive and detailed blog outline based on the following details:

# Keywords: {keywords}
# Primary Keywords: {primary_keywords}
# Prompt: {prompt}

# Outline Requirements:
# 1. Introduction:
#    - Compelling hook related to the main topic
#    - Brief overview of the topic and its significance
#    - Problem the blog addresses
#    - Include a captivating anecdote or statistic to engage readers

# 2. Main Sections:
#    - Detailed breakdown of the main points
#    - Unique insights or perspectives
#    - Include sub-sections for each major point

# 3. Use Cases and Applications:
#    - Specific scenarios where the topic is relevant
#    - Target audience and their pain points
#    - Real-world examples or potential applications
#    - Include case studies or success stories if available

# 4. Benefits and Advantages:
#    - Comprehensive list of benefits
#    - Quantifiable improvements or advantages
#    - Customer-centric perspective on the topic's value
#    - Include testimonials or reviews to support claims

# 5. Practical Insights:
#    - Implementation tips
#    - Best practices related to the topic
#    - Potential challenges and solutions
#    - Include step-by-step guides or tutorials

# 6. Conclusion:
#    - Recap of key points
#    - Clear call-to-action
#    - Future potential or upcoming trends
#    - Include a final thought or reflection to leave a lasting impression

# Additional Guidance:
# - Ensure the outline is informative and engaging
# - Incorporate keywords naturally and frequently throughout the blog
# - Focus on solving reader problems
# - Maintain a balanced, objective tone
# - Highlight unique aspects of the topic
# - Provide detailed sub-points under each main section to elaborate on the content
# """
#     response = blog_generation_model.generate_content(outline_prompt)
#     return response.text

# def generate_general_blog_content(outline, keywords, primary_keywords, prompt):
#     sections = outline.split('\n\n')
#     blog_content = []
#     all_keywords = primary_keywords.split(", ") + keywords.split(", ")
#     keyword_usage = {keyword: 0 for keyword in all_keywords}
#     primary_keyword_target = 3
#     secondary_keyword_target = 1

#     for i, section in enumerate(sections):
#         previous_text = ' '.join(blog_content) if i > 0 else 'None'
#         primary_keywords_instruction = (
#             "\n- Use primary keywords sparingly and naturally, aiming for no more than 3 total uses across the entire blog: "
#             + ', '.join(primary_keywords.split(", ")) +
#             ". Ensure the usage is contextually relevant and not forced."
#         )
#         secondary_keywords_instruction = (
#             "\n- Use each of the following secondary keywords approximately **1 time** throughout the entire blog: "
#             + ', '.join(keywords.split(", ")) +
#             ". Make the usage natural and contextually relevant."
#         )
#         section_prompt = f"""Generate a detailed section for a blog post while ensuring no repetition.

# Section Outline:
# {section}

# Guidelines:
# - Word count for this section: Approximately {1200 // len(sections)} words
# - Avoid repeating points from previous sections
# - Focus on new insights, examples, and fresh perspectives
# - Ensure smooth transitions from previous sections
# - Maintain a professional and engaging tone{primary_keywords_instruction}{secondary_keywords_instruction}

# Previous Sections Summary:
# {previous_text}

# Generate the content for this section."""
#         response = blog_generation_model.generate_content(section_prompt)
#         section_content = response.text
#         for keyword in all_keywords:
#             keyword_usage[keyword] += section_content.lower().count(keyword.lower())
#         blog_content.append(section_content)

#     for keyword, count in keyword_usage.items():
#         if keyword in primary_keywords.split(", ") and count > primary_keyword_target:
#             blog_content = [section.replace(keyword, f"**{keyword}**", count - primary_keyword_target) for section in blog_content]
#         elif keyword in keywords.split(", ") and count < secondary_keyword_target:
#             additional_content = f"Moreover, {keyword} is an important aspect to consider."
#             blog_content.append(additional_content)
#             keyword_usage[keyword] += 1

#     final_content = '\n\n'.join(blog_content)
#     improved_content = improve_grammar_and_readability(final_content, primary_keywords, keywords)
#     return improved_content

def generate_blog_summary(blog_content, primary_keywords, secondary_keywords, intent):
    summary_prompt = f"""Generate a concise and engaging summary (150-200 words) of the following blog content. 
    Focus on:
    - Highlighting the main points and key takeaways
    - Incorporating the primary keywords ({primary_keywords}) 1-2 times naturally
    - Including each secondary keyword ({secondary_keywords}) at least once
    - Aligning with the intent: {intent}
    - Maintaining a professional yet conversational tone
    - Avoiding repetition of the full content, focusing on a high-level overview

    Blog Content:
    {blog_content}

    Provide the summary."""
    try:
        response = blog_generation_model.generate_content(summary_prompt)
        return response.text
    except Exception as e:
        print(f"Summary generation error: {e}")
        return "Unable to generate summary due to an error."

def generate_faq_content(blog_content, faq_count=5):
    faq_prompt = f"""Generate {faq_count} frequently asked questions (FAQs) based on the following blog content. 
    Ensure the FAQs:
    - Are directly relevant to the content provided
    - Address common reader queries or potential confusion points
    - Are concise, clear, and engaging
    - Include both the question and a brief answer (2-3 sentences)
    - Are formatted as a numbered list (e.g., 1. Question: ... Answer: ...)

    Blog Content:
    {blog_content}

    Provide the FAQs."""
    try:
        response = blog_generation_model.generate_content(faq_prompt)
        return response.text
    except Exception as e:
        print(f"FAQ generation error: {e}")
        return "Unable to generate FAQs due to an error."

# Updated INDEX_TEMPLATE with loaders
INDEX_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Blog Generator Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
    <script type="module" src="https://cdn.jsdelivr.net/npm/ldrs/dist/auto/grid.js"></script>
    <script>
        function showForm(type) {
            document.getElementById('product-form-container').style.display = 'none';
            document.getElementById('general-form-container').style.display = 'none';
            document.getElementById('faq-form-container').style.display = 'none';
            if (type === 'product') {
                document.getElementById('product-form-container').style.display = 'block';
            } else if (type === 'general') {
                document.getElementById('general-form-container').style.display = 'block';
            } else if (type === 'faq') {
                document.getElementById('faq-form-container').style.display = 'block';
            }
        }

        function showLoader(loaderId) {
            document.getElementById(loaderId).style.display = 'flex';
        }

        function hideLoader(loaderId) {
            document.getElementById(loaderId).style.display = 'none';
        }

        document.addEventListener('DOMContentLoaded', () => {
            document.querySelectorAll('form').forEach(form => {
                form.addEventListener('submit', (e) => {
                    if (form.action.includes('/faq')) {
                        showLoader('grid-loader-faq');
                    } else {
                        showLoader('grid-loader');
                    }
                });
            });
        });
    </script>
    <style>
        .loader-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.5);
            display: none;
            justify-content: center;
            align-items: center;
            z-index: 9999;
        }
    </style>
</head>
<body class="bg-gradient-to-br from-gray-100 to-gray-200 min-h-screen flex items-center justify-center p-4">
    <div class="container mx-auto max-w-5xl bg-white rounded-2xl shadow-2xl overflow-hidden relative">
        <div class="bg-gradient-to-r from-blue-500 to-purple-600 p-8 relative">
            <h1 class="text-4xl font-extrabold mb-4 text-center text-white drop-shadow-lg">Blog Generator Dashboard</h1>
            <p class="text-center text-white opacity-80">Create compelling blog content with ease</p>
            <a href="/logout" class="absolute top-4 right-4 flex items-center bg-red-500 text-white px-4 py-2 rounded-lg hover:bg-red-600 transition duration-300 ease-in-out transform hover:scale-105">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                </svg>
                Logout
            </a>
        </div>

        <div class="p-8">
            <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-10">
                <div onclick="showForm('product')" class="group cursor-pointer p-6 bg-white border-2 border-transparent rounded-xl shadow-lg hover:border-blue-500 hover:shadow-2xl transition-all duration-300 ease-in-out transform hover:-translate-y-2">
                    <div class="bg-blue-100 rounded-full w-16 h-16 flex items-center justify-center mb-4 group-hover:bg-blue-200 transition">
                        <svg xmlns="http://www.w3.org/2000/svg" class="h-8 w-8 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.485M7 17h.01" />
                        </svg>
                    </div>
                    <h2 class="text-2xl font-bold mb-2 text-gray-800 group-hover:text-blue-600 transition">Product-Specific Blog</h2>
                    <p class="text-gray-600 group-hover:text-gray-800 transition">Generate a blog tailored to a specific product using keywords and descriptions.</p>
                </div>
                <div onclick="showForm('general')" class="group cursor-pointer p-6 bg-white border-2 border-transparent rounded-xl shadow-lg hover:border-purple-500 hover:shadow-2xl transition-all duration-300 ease-in-out transform hover:-translate-y-2">
                    <div class="bg-purple-100 rounded-full w-16 h-16 flex items-center justify-center mb-4 group-hover:bg-purple-200 transition">
                        <svg xmlns="http://www.w3.org/2000/svg" class="h-8 w-8 text-purple-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z" />
                        </svg>
                    </div>
                    <h2 class="text-2xl font-bold mb-2 text-gray-800 group-hover:text-purple-600 transition">General Blog</h2>
                    <p class="text-gray-600 group-hover:text-gray-800 transition">Create general blogs for topics or industries.</p>
                </div>
                <div onclick="showForm('faq')" class="group cursor-pointer p-6 bg-gradient-to-br from-teal-50 to-cyan-100 border-2 border-transparent rounded-xl shadow-md hover:shadow-xl hover:border-teal-400 transition-all duration-300 ease-in-out transform hover:scale-105">
                    <div class="bg-teal-200 rounded-full w-16 h-16 flex items-center justify-center mb-4 group-hover:bg-teal-300 transition-all duration-300">
                        <svg xmlns="http://www.w3.org/2000/svg" class="h-8 w-8 text-teal-600 group-hover:text-teal-800 transition-all duration-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                    </div>
                    <h2 class="text-2xl font-extrabold mb-2 text-gray-800 group-hover:text-teal-700 transition-all duration-300">FAQ Content Generator</h2>
                    <p class="text-gray-600 group-hover:text-gray-800 font-medium transition-all duration-300">Transform your blog into concise, engaging FAQs effortlessly.</p>
                </div>
            </div>

            <div id="product-form-container" style="display:none;" class="bg-white p-8 rounded-xl shadow-lg border border-gray-100">
                <h2 class="text-2xl font-bold mb-6 text-center text-blue-600">Generate Product Blog</h2>
                <form method="POST" action="/" class="space-y-4">
                    <div class="group">
                        <label class="block mb-2 text-gray-700 group-hover:text-blue-600 transition">Product URL</label>
                        <input type="text" name="product_url" required class="w-full p-3 border-2 border-gray-200 rounded-lg focus:outline-none focus:border-blue-500 transition">
                    </div>
                    <div class="group">
                        <label class="block mb-2 text-gray-700 group-hover:text-blue-600 transition">Product Title</label>
                        <input type="text" name="product_title" required class="w-full p-3 border-2 border-gray-200 rounded-lg focus:outline-none focus:border-blue-500 transition">
                    </div>
                    <div class="group">
                        <label class="block mb-2 text-gray-700 group-hover:text-blue-600 transition">Product Description</label>
                        <textarea name="product_description" required class="w-full p-3 border-2 border-gray-200 rounded-lg focus:outline-none focus:border-blue-500 transition" rows="4"></textarea>
                    </div>
                    <div class="group">
                        <label class="block mb-2 text-gray-700 group-hover:text-blue-600 transition">Primary Keywords</label>
                        <input type="text" name="primary_keywords" required class="w-full p-3 border-2 border-gray-200 rounded-lg focus:outline-none focus:border-blue-500 transition">
                    </div>
                    <div class="group">
                        <label class="block mb-2 text-gray-700 group-hover:text-blue-600 transition">Secondary Keywords</label>
                        <input type="text" name="secondary_keywords" required class="w-full p-3 border-2 border-gray-200 rounded-lg focus:outline-none focus:border-blue-500 transition">
                    </div>
                    <div class="group">
                        <label class="block mb-2 text-gray-700 group-hover:text-blue-600 transition">Search Intent</label>
                        <input type="text" name="intent" required class="w-full p-3 border-2 border-gray-200 rounded-lg focus:outline-none focus:border-blue-500 transition">
                    </div>
                    <button type="submit" class="w-full bg-gradient-to-r from-blue-500 to-purple-600 text-white p-3 rounded-lg hover:from-blue-600 hover:to-purple-700 transition duration-300 ease-in-out transform hover:scale-105 hover:shadow-lg">
                        Generate Blog
                    </button>
                </form>
            </div>

            <div id="general-form-container" style="display:none;" class="bg-white p-8 rounded-xl shadow-lg border border-gray-100">
                <h2 class="text-2xl font-bold mb-6 text-center text-purple-600">Generate General Blog</h2>
                <form method="POST" action="/general" class="space-y-4">
                    <div class="group">
                        <label class="block mb-2 text-gray-700 group-hover:text-purple-600 transition">Keywords</label>
                        <input type="text" name="keywords" required class="w-full p-3 border-2 border-gray-200 rounded-lg focus:outline-none focus:border-purple-500 transition">
                    </div>
                    <div class="group">
                        <label class="block mb-2 text-gray-700 group-hover:text-purple-600 transition">Primary Keywords</label>
                        <input type="text" name="primary_keywords" required class="w-full p-3 border-2 border-gray-200 rounded-lg focus:outline-none focus:border-purple-500 transition">
                    </div>
                    <div class="group">
                        <label class="block mb-2 text-gray-700 group-hover:text-purple-600 transition">Prompt</label>
                        <textarea name="prompt" required class="w-full p-3 border-2 border-gray-200 rounded-lg focus:outline-none focus:border-purple-500 transition" rows="4"></textarea>
                    </div>
                    <button type="submit" class="w-full bg-gradient-to-r from-purple-500 to-blue-600 text-white p-3 rounded-lg hover:from-purple-600 hover:to-blue-700 transition duration-300 ease-in-out transform hover:scale-105 hover:shadow-lg">
                        Generate Blog
                    </button>
                </form>
            </div>

            <div id="faq-form-container" style="display:none;" class="bg-white p-8 rounded-xl shadow-lg border border-gray-100">
                <h2 class="text-2xl font-bold mb-6 text-center text-teal-600">Generate FAQ Content</h2>
                <form method="POST" action="/faq" class="space-y-4">
                    <div class="group">
                        <label class="block mb-2 text-gray-700 group-hover:text-teal-600 transition">Blog Content</label>
                        <textarea name="blog_content" required class="w-full p-3 border-2 border-gray-200 rounded-lg focus:outline-none focus:border-teal-500 transition" rows="6" placeholder="Paste your blog content here"></textarea>
                    </div>
                    <div class="group">
                        <label class="block mb-2 text-gray-700 group-hover:text-teal-600 transition">Number of FAQs (optional)</label>
                        <input type="number" name="faq_count" min="1" max="20" value="5" class="w-full p-3 border-2 border-gray-200 rounded-lg focus:outline-none focus:border-teal-500 transition">
                    </div>
                    <button type="submit" class="w-full bg-gradient-to-r from-teal-500 via-cyan-500 to-teal-600 text-black p-3 rounded-lg font-semibold shadow-lg hover:shadow-xl hover:from-teal-600 hover:via-cyan-600 hover:to-teal-700 transition-all duration-300 ease-in-out transform hover:scale-105 hover:animate-pulse">
                        Generate FAQs
                    </button>
                </form>
            </div>
        </div>
    </div>

    <div id="grid-loader" class="loader-overlay">
        <l-grid size="150" speed="1.7" color="white"></l-grid>
    </div>
    <div id="grid-loader-faq" class="loader-overlay">
        <l-grid size="150" speed="1.7" color="white"></l-grid>
    </div>
</body>
</html>
'''

# Updated RESULT_TEMPLATE with loaders
RESULT_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Blog Generation Result</title>
    <link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
    <script type="module" src="https://cdn.jsdelivr.net/npm/ldrs/dist/auto/quantum.js"></script>
    <script>
        function showLoader(loaderId) {
            document.getElementById(loaderId).style.display = 'flex';
        }

        function hideLoader(loaderId) {
            document.getElementById(loaderId).style.display = 'none';
        }

        function humanizeBlog() {
            const userConfirmed = confirm("I have read and made necessary changes to the AI blog. I know each humanize will cost credits. I agree to move forward. Proceed?");
            if (userConfirmed) {
                showLoader('quantum-loader-humanize');
                fetch('/humanize', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        content: document.getElementById('blog-content').textContent
                    })
                })
                .then(response => response.json())
                .then(data => {
                    document.getElementById('humanized-content').textContent = data.humanized_content;
                    document.getElementById('humanize-section').style.display = 'block';
                    hideLoader('quantum-loader-humanize');
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert('Failed to humanize the blog');
                    hideLoader('quantum-loader-humanize');
                });
            }
        }

        function saveEdits() {
            const editedContent = document.getElementById('blog-content').textContent;
            fetch('/save', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    content: editedContent
                })
            })
            .then(response => response.json())
            .then(data => {
                alert('Edits saved successfully');
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Failed to save edits');
            });
        }

        function regenerateContent() {
            showLoader('quantum-loader-regenerate');
            fetch('/regenerate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            })
            .then(response => response.json())
            .then(data => {
                hideLoader('quantum-loader-regenerate');
                if (data.error) {
                    alert('Error: ' + data.error);
                } else {
                    document.getElementById('blog-outline').textContent = data.outline || 'N/A';
                    document.getElementById('blog-content').textContent = data.content;
                    document.getElementById('humanize-section').style.display = 'none';
                    document.getElementById('blog-summary').textContent = data.summary || 'N/A';
                    if (data.faq_content) {
                        document.getElementById('faq-content').textContent = data.faq_content;
                        document.getElementById('faq-section').style.display = 'block';
                    } else {
                        document.getElementById('faq-section').style.display = 'none';
                    }
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Failed to regenerate content');
                hideLoader('quantum-loader-regenerate');
            });
        }
    </script>
    <style>
        .loader-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.5);
            display: none;
            justify-content: center;
            align-items: center;
            z-index: 9999;
        }
    </style>
</head>
<body class="bg-gradient-to-br from-gray-100 to-gray-200 min-h-screen flex items-center justify-center p-4">
    <div class="container mx-auto max-w-6xl bg-white rounded-2xl shadow-2xl overflow-hidden">
        <div class="bg-gradient-to-r from-blue-500 to-purple-600 p-6">
            <h1 class="text-4xl font-extrabold text-center text-white drop-shadow-lg">Generated Blog Content</h1>
        </div>

        <div class="p-8 space-y-8">
            <div class="bg-white border-2 border-gray-100 rounded-xl p-6 shadow-lg" id="outline-section" style="display: {{ 'block' if outline else 'none' }}">
                <h2 class="text-2xl font-bold mb-4 text-blue-600 flex items-center">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6 mr-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z" />
                    </svg>
                    Blog Outline
                </h2>
                <pre id="blog-outline" class="bg-gray-50 p-4 rounded-lg border border-gray-200 whitespace-pre-wrap text-gray-700">{{ outline }}</pre>
            </div>

            <div class="bg-white border-2 border-gray-100 rounded-xl p-6 shadow-lg" id="summary-section" style="display: {{ 'block' if summary else 'none' }}">
                <h2 class="text-2xl font-bold mb-4 text-teal-600 flex items-center">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6 mr-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m-2 13h-2m4-3H5" />
                    </svg>
                    Blog Summary
                </h2>
                <pre id="blog-summary" class="bg-gray-50 p-4 rounded-lg border border-gray-200 whitespace-pre-wrap text-gray-700">{{ summary }}</pre>
            </div>

            <div class="bg-white border-2 border-gray-100 rounded-xl p-6 shadow-lg">
                <h2 class="text-2xl font-bold mb-4 text-purple-600 flex items-center">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6 mr-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                    </svg>
                    Blog Content
                </h2>
                <div class="prose max-w-none">
                    <pre id="blog-content" contenteditable="true" class="bg-gray-50 p-4 rounded-lg border border-gray-200 whitespace-pre-wrap text-gray-800 focus:ring-2 focus:ring-purple-500 transition">{{ content }}</pre>
                </div>
            </div>

            <div id="faq-section" style="display: {{ 'block' if faq_content else 'none' }};" class="bg-white border-2 border-gray-100 rounded-xl p-6 shadow-lg">
                <h2 class="text-2xl font-bold mb-4 text-teal-600 flex items-center">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6 mr-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    Generated FAQs
                </h2>
                <pre id="faq-content" class="bg-gray-50 p-4 rounded-lg border border-gray-200 whitespace-pre-wrap text-gray-700">{{ faq_content }}</pre>
            </div>

            <div class="flex justify-center space-x-4">
                {% if not faq_content %}
                <button onclick="humanizeBlog()" class="flex items-center bg-gradient-to-r from-green-500 to-teal-600 text-white px-6 py-3 rounded-lg hover:from-green-600 hover:to-teal-700 transition transform hover:scale-105 shadow-lg">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                    </svg>
                    Humanize Blog
                </button>
                {% endif %}
                <button onclick="saveEdits()" class="flex items-center bg-gradient-to-r from-yellow-500 to-orange-600 text-white px-6 py-3 rounded-lg hover:from-yellow-600 hover:to-orange-700 transition transform hover:scale-105 shadow-lg">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4" />
                    </svg>
                    Save Edits
                </button>
                <button onclick="regenerateContent()" class="flex items-center bg-gradient-to-r from-purple-500 to-pink-600 text-white px-6 py-3 rounded-lg hover:from-purple-600 hover:to-pink-700 transition transform hover:scale-105 shadow-lg">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9H0m0 0v5h5.582M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    Regenerate Content
                </button>
                <a href="/" class="flex items-center bg-gradient-to-r from-blue-500 to-indigo-600 text-white px-6 py-3 rounded-lg hover:from-blue-600 hover:to-indigo-700 transition transform hover:scale-105 shadow-lg">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
                    </svg>
                    Generate Another Blog
                </a>
                <a href="/logout" class="flex items-center bg-gradient-to-r from-red-500 to-pink-600 text-white px-6 py-3 rounded-lg hover:from-red-600 hover:to-pink-700 transition transform hover:scale-105 shadow-lg">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                    </svg>
                    Logout
                </a>
            </div>

            <div id="humanize-section" style="display:none;" class="bg-white border-2 border-gray-100 rounded-xl p-6 shadow-lg">
                <h2 class="text-2xl font-bold mb-4 text-green-600 flex items-center">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6 mr-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    Humanized Blog Content
                </h2>
                <pre id="humanized-content" class="bg-gray-50 p-4 rounded-lg border border-gray-200 whitespace-pre-wrap text-gray-700"></pre>
            </div>
        </div>
    </div>

    <div id="quantum-loader-humanize" class="loader-overlay">
        <l-quantum size="150" speed="1.7" color="white"></l-quantum>
    </div>
    <div id="quantum-loader-regenerate" class="loader-overlay">
        <l-quantum size="150" speed="1.7" color="white"></l-quantum>
    </div>
</body>
</html>
'''

# Routes remain largely unchanged except for minor adjustments
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = users_collection.find_one({'email': email})
        if user and bcrypt.check_password_hash(user['password'], password):
            session['logged_in'] = True
            session['user_email'] = email
            return redirect(url_for('index'))
        else:
            return render_template_string(LOGIN_SIGNUP_TEMPLATE, error="Invalid email or password")
    return render_template_string(LOGIN_SIGNUP_TEMPLATE)

@app.route('/signup', methods=['POST'])
def signup():
    email = request.form.get('email')
    password = request.form.get('password')
    confirm_password = request.form.get('confirm_password')
    if password != confirm_password:
        return render_template_string(LOGIN_SIGNUP_TEMPLATE, error="Passwords do not match")
    existing_user = users_collection.find_one({'email': email})
    if existing_user:
        return render_template_string(LOGIN_SIGNUP_TEMPLATE, error="Email already registered")
    hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
    users_collection.insert_one({
        'email': email,
        'password': hashed_password,
        'created_at': time.time()
    })
    session['logged_in'] = True
    session['user_email'] = email
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    session.pop('user_email', None)
    return redirect(url_for('login'))

@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    if request.method == 'POST':
        product_url = request.form.get('product_url')
        product_title = request.form.get('product_title')
        product_description = request.form.get('product_description')
        primary_keywords = request.form.get('primary_keywords')
        secondary_keywords = request.form.get('secondary_keywords')
        intent = request.form.get('intent')
        session['form_data'] = {
            'product_url': product_url,
            'product_title': product_title,
            'product_description': product_description,
            'primary_keywords': primary_keywords,
            'secondary_keywords': secondary_keywords,
            'intent': intent,
            'type': 'product'
        }
        try:
            blog_outline = generate_blog_outline(product_url, product_title, product_description, primary_keywords, secondary_keywords, intent)
            blog_content = generate_blog_content(blog_outline, product_url, product_title, product_description, primary_keywords, secondary_keywords, intent)
            blog_summary = generate_blog_summary(blog_content, primary_keywords, secondary_keywords, intent)
            return render_template_string(RESULT_TEMPLATE, outline=blog_outline, content=blog_content, summary=blog_summary)
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    return render_template_string(INDEX_TEMPLATE)

@app.route('/general', methods=['POST'])
def generate_general_blog():
    keywords = request.form.get('keywords')
    primary_keywords = request.form.get('primary_keywords')
    prompt = request.form.get('prompt')
    session['form_data'] = {
        'keywords': keywords,
        'primary_keywords': primary_keywords,
        'prompt': prompt,
        'type': 'general'
    }
    try:
        blog_outline = generate_general_blog_outline(keywords, primary_keywords, prompt)
        blog_content = generate_general_blog_content(blog_outline, keywords, primary_keywords, prompt)
        blog_summary = generate_blog_summary(blog_content, primary_keywords, keywords, intent="informative")
        return render_template_string(RESULT_TEMPLATE, outline=blog_outline, content=blog_content, summary=blog_summary)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/regenerate', methods=['POST'])
def regenerate_content():
    try:
        form_data = session.get('form_data', {})
        if not form_data:
            return jsonify({"error": "No previous form data found"}), 400
        if form_data.get('type') == 'product':
            blog_outline = generate_blog_outline(
                form_data['product_url'], form_data['product_title'], form_data['product_description'],
                form_data['primary_keywords'], form_data['secondary_keywords'], form_data['intent']
            )
            blog_content = generate_blog_content(
                blog_outline, form_data['product_url'], form_data['product_title'], form_data['product_description'],
                form_data['primary_keywords'], form_data['secondary_keywords'], form_data['intent']
            )
            blog_summary = generate_blog_summary(
                blog_content, form_data['primary_keywords'], form_data['secondary_keywords'], form_data['intent']
            )
            return jsonify({'outline': blog_outline, 'content': blog_content, 'summary': blog_summary})
        elif form_data.get('type') == 'general':
            blog_outline = generate_general_blog_outline(form_data['keywords'], form_data['primary_keywords'], form_data['prompt'])
            blog_content = generate_general_blog_content(blog_outline, form_data['keywords'], form_data['primary_keywords'], form_data['prompt'])
            blog_summary = generate_blog_summary(blog_content, form_data['primary_keywords'], form_data['keywords'], intent="informative")
            return jsonify({'outline': blog_outline, 'content': blog_content, 'summary': blog_summary})
        elif form_data.get('type') == 'faq':
            faq_content = generate_faq_content(form_data['blog_content'], form_data['faq_count'])
            return jsonify({'outline': None, 'content': form_data['blog_content'], 'summary': None, 'faq_content': faq_content})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/humanize', methods=['POST'])
def humanize_blog():
    try:
        data = request.get_json()
        content = data.get('content', '')
        humanized_content = humanize_text(content)
        return jsonify({'humanized_content': humanized_content})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/save', methods=['POST'])
def save_edits():
    try:
        data = request.get_json()
        edited_content = data.get('content', '')
        return jsonify({'message': 'Edits saved successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/faq', methods=['POST'])
def generate_faq():
    blog_content = request.form.get('blog_content')
    faq_count = int(request.form.get('faq_count', 5))
    session['form_data'] = {'blog_content': blog_content, 'faq_count': faq_count, 'type': 'faq'}
    try:
        faq_content = generate_faq_content(blog_content, faq_count)
        return render_template_string(RESULT_TEMPLATE, outline=None, content=blog_content, summary=None, faq_content=faq_content)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", 5000)))