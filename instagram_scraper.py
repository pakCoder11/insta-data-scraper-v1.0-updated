from email import message
from math import ceil
from selenium_driverless import webdriver
from selenium_driverless.types.by import By
from multiprocessing import Pool
import asyncio 
import pyautogui
from dotenv import load_dotenv
import os
from bs4 import BeautifulSoup
import random
import bot_functions
import time
import re
import data_store
import pandas as pd
import ai_function
import sys
import json
import urllib.request

# Push a log line to the Flask app so it can broadcast via Socket.IO
def push_log(msg):
    try:
        data = json.dumps({"message": str(msg)}).encode("utf-8")
        req = urllib.request.Request(
            "http://127.0.0.1:5000/api/push-log",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        # keep it non-blocking-ish with a small timeout
        urllib.request.urlopen(req, timeout=1.5).read()
    except Exception:
        # swallow any network error to avoid breaking scraping flow
        pass

# Redirect child process stdout/stderr so print() lines also go to Live Logs
def _child_redirect_init():
    class _HTTPWriter:
        def __init__(self, original):
            self.original = original
            self.buf = ''
        def write(self, s):
            # write-through to original
            try:
                self.original.write(s)
            except Exception:
                pass
            # buffer and send complete lines
            self.buf += s
            while '\n' in self.buf:
                line, self.buf = self.buf.split('\n', 1)
                line = line.rstrip('\r')
                if line:
                    push_log(line)
            return len(s)
        def flush(self):
            try:
                self.original.flush()
            except Exception:
                pass
    sys.stdout = _HTTPWriter(sys.stdout)
    sys.stderr = _HTTPWriter(sys.stderr)

# Make file logging append and also emit to Live Logs
def write_logs_to_file(str):
    try:
        with open('logs.txt', 'a', encoding='utf-8') as f:
            f.write(str + "\n")
    except Exception:
        pass
    try:
        push_log(str)
    except Exception:
        pass

def to_english_instagram_url(url):
    """
    Converts an Instagram URL to enforce English language support (?hl=en).
    """
    if '?hl=en' in url:
        return url
    if '?' in url:
        return url + '&hl=en'
    else:
        return url + '?hl=en'

async def switch_to_latest_post(list_of_accounts,driver):

    """
    This function is used to switch on the latest post ... 
    """

    random_url = random.choice(list_of_accounts)

    # counter = 0
    await driver.get(to_english_instagram_url(random_url))
    await asyncio.sleep(3)  # Wait for the page to load             

    pyautogui.press('tab')
    pyautogui.press('tab')
    pyautogui.press('tab')
    pyautogui.press('tab')

    bot_functions.press_down_keys(3)

    bot_functions.ClickImageOnScreen("./Screenshots/grid.png",1)  
    time.sleep(4)

    bot_functions.press_tab_key(5)

    pyautogui.press('enter')
    time.sleep(2)
    bot_functions.press_left_keys(10)

    time.sleep(2)  # Wait for the page to load

async def post_comment(driver,comments_list):

    try:

        comment_field = await driver.find_element(By.XPATH, "//textarea[@aria-label='Add a comment…']")
        await comment_field.click()
        comment = random.choice(comments_list)
        pyautogui.write(comment)
        await asyncio.sleep(2) 
        write_logs_to_file(f"This comment {comment} is posted successfully on a post")

        pyautogui.press('space') 
        time.sleep(2)
        pyautogui.press('enter') 
        time.sleep(2)

        xpaths = [
        "//button[.//svg[@aria-label='Next']]",                           
        "//button[.//svg/title[text()='Next']]",                         
        "//svg[@aria-label='Next']/ancestor::button",                    
        "//button[.//*[text()='Next' or @aria-label='Next']]",            
        "//button[@class='_abl-']",                                       
        "(//button[@class='_abl-'])[last()]",                             
        "//button[.//svg[@role='img' and @aria-label='Next']]",           
        ]

        for xpath in xpaths:

            try:

                next_button = await driver.find_element(By.XPATH, xpath)
                await next_button.click() 
                break
            
            except Exception as e:
                # print("Next button XPATH not found...")
                write_logs_to_file("Next button XPATH not found...")

        # await asyncio.sleep(5)
    
    except Exception as e:
        # print(f"XPATH not found ...{e}") 
        write_logs_to_file(f"XPATH not found ...{e}")

async def login_to_instagram(driver,username,password):

    # print("Logging in to Instagram... function...")

    # Navigate to Instagram login page
    await driver.get("https://www.instagram.com/accounts/login/")
    await asyncio.sleep(3)  # Wait for page to load
            
    # Find username field by aria-label text using XPath
    username_xpath = "//input[@aria-label='Phone number, username, or email']"
    username_field = await driver.find_element(By.XPATH, username_xpath)
    await username_field.click()
    await username_field.clear()
    await username_field.send_keys(username)
            
    # Find password field by aria-label text using XPath
    password_xpath = "//input[@aria-label='Password']"
    password_field = await driver.find_element(By.XPATH, password_xpath)
    await password_field.click()
    await password_field.clear()
    await password_field.send_keys(password)

    login_button_xpath = "//button[@type='submit']"
    login_button = await driver.find_element(By.XPATH, login_button_xpath)
    await login_button.click()

    # Wait for and handle "Not now" button if it appears
    not_now_button = await wait_for_not_now_button(driver)

    if not_now_button: 
        await not_now_button.click()
        write_logs_to_file("Successfully login to Instagram account")

async def write_comments_on_instagram_posts(login_account_dict,list_of_profile,number_of_comments,comments_to_post_list):

    # it will select a random account and post url it will paste comments on that account posts repetively

    usernames = login_account_dict['usernames_list']
    passwords = login_account_dict['passwords_list']

    load_dotenv()
    # username = os.getenv("INSTAGRAM_USERNAME")
    # password = os.getenv("INSTAGRAM_PASSWORD")

    options = webdriver.ChromeOptions()
    options.add_argument("--icognito")

    # New code for sigin-in with mutiple accounts ...
    counter = 0


    for x in range(0,len(usernames)):
        async with webdriver.Chrome(options=options) as driver:

            try:

                await login_to_instagram(driver,usernames[x],passwords[x])

                await switch_to_latest_post(list_of_profile,driver) 
                while(True):
            
                    await asyncio.sleep(2)                      
                    await post_comment(driver,comments_to_post_list) 
                    time.sleep(45) 

                    pyautogui.press('right')
                    counter += 1
                    if counter == number_of_comments: 
                        break
                    # print(f"The counter is {counter}")

            except Exception as e:
                pass

def extract_comments_data(html,url):
    soup = BeautifulSoup(html, 'html.parser')
    comments = []

    # Find all comment blocks
    for comment_block in soup.find_all('div', class_='_a9zm'):
        # Find the child div with class '_a9zo'
        child = comment_block.find('div', class_='_a9zo')
        if not child:
            continue

        # Extract username and profile link
        user_a = child.find('a', href=True)
        if user_a:
            # username = user_a.text.strip() 
            username = '@'+ user_a['href'].replace("/","")

            profile_link = 'https://www.instagram.com' + user_a['href']
        else:
            username = None
            profile_link = None

        # Extract comment text
        comment_text_tag = child.find('span', class_='_ap3a')
        comment_text = comment_text_tag.text.strip() if comment_text_tag else None

        # Extract time
        time_tag = child.find('time', class_='_a9ze')
        time_of_comment = time_tag.get('title') if time_tag and time_tag.has_attr('title') else None

        # Store in dictionary
        comment_dict = {
            'username': username,
            'profile_link': profile_link,
            'comment_text': comment_text,
            'time_of_comment': time_of_comment, 
            'post_url' : url
        }

        data_store.store_to_json(comment_dict,'comments_data.json')
        comments.append(comment_dict)

    return comments

def scrap_caption_likes_and_post_time(html_content):

    profile_data_dict = {'post_caption' : None,'likes' : None, 'hashtags' : None, 'time' : None, 'post_url' : None}

    soup = BeautifulSoup(html_content, 'html.parser')
    # Extracting post description
    post_description_tag = soup.find('h1', class_='_ap3a _aaco _aacu _aacx _aad7 _aade')
    post_description = post_description_tag.text.strip() if post_description_tag else ''

    hashtags = re.findall(r'#\w+', post_description)

    if hashtags:
        profile_data_dict['hashtags'] = hashtags
    
    else:
        profile_data_dict['hashtags'] = '---'

    profile_data_dict['post_caption'] = post_description

    # return profile_data_dict
    """
    Extracts likes count from Instagram post HTML
    Args:
        html: HTML source code containing Instagram like count
    Returns:
        int: Number of likes (cleaned and converted to integer)
    """
    
    # Find the likes link element

    likes_div = soup.find_all('a')

    for ld in likes_div:

        if ld['href'].find('/liked_by/') > 0: 
            like_string = ld.span.text.strip()
            profile_data_dict['likes'] = like_string

    """
    likes_link = soup.find('a', href=lambda x: x and '/liked_by/' in x) 
    print(likes_link.a.span.text)
    if not likes_link:

        profile_data_dict['likes'] = 'not mentioned'
    # Get the text from the span inside the link
    span_text = likes_link.find('span', class_='x193iq5w').text.strip()
    # print(span_text)

    # Extract numbers from the text
    # Handle both cases:
    # Case 1: "28,787 likes"
    # Case 2: "user1, user2 and 23,456 others"

    numbers = re.findall(r'[\d,]+', span_text)
    if numbers:
        # Take the last number found (works for both cases)
        likes_str = numbers[-1]
        # Remove commas and convert to integer
        # return int(likes_str.replace(',', ''))
        # print(f"Total likes are {likes_str}")
        profile_data_dict['likes'] = int(likes_str.replace(',', ''))
    """

    time_tag = soup.find('time', class_='x1p4m5qa')
    if time_tag:
        # datetime_attr = time_tag.get('datetime')
        readable_time = time_tag.get('title') 
        # add a logic ... 
        profile_data_dict['time'] = f'{readable_time}'

    # return 0


    return profile_data_dict

def extract_instagram_posts_links(html):
    """
    Extracts Instagram post URLs from HTML source code
    Args:
        html: HTML source code containing Instagram links
    Returns:
        list: List of complete Instagram URLs
    """
    soup = BeautifulSoup(html, 'html.parser')
    links = []
    
    # Find all 'a' tags that match Instagram's link pattern
    for a in soup.find_all('a', attrs={'role': 'link'}):
        href = a.get('href')
        if href and '/p/' in href:  # Instagram post URLs contain '/p/'
            # Convert relative URL to absolute URL and add language parameter
            clean_path = href.strip('/')
            full_url = f"https://instagram.com/{clean_path}?hl=en"
            links.append(full_url)
    
    return links[0]

async def wait_for_not_now_button(driver):
    """
    Waits for and returns the "Not now" button element when it appears
    Args:
        driver: The selenium-driverless webdriver instance
    Returns:
        The button element if found, None if timeout occurs
    """
    try:
        # XPath to find the div with exact text "Not now"
        not_now_xpath = "//div[@role='button'][contains(text(), 'Not now')]"
        
        # Wait up to 10 seconds for the element
        await asyncio.sleep(2)  # Initial small delay
        
        for _ in range(10):  # Try up to 5 times (total 10 seconds)
            try:
                not_now_button = await driver.find_element(By.XPATH, not_now_xpath)
                if not_now_button:
                    return not_now_button
            except:
                await asyncio.sleep(2)  # Wait 2 seconds before trying again
        return None
        
    except Exception as e:
        print(f"Error waiting for 'Not now' button: {e}")
        return None



def move_to_first_post():

    time.sleep(7)

    bot_functions.press_tab_key(4) 
    time.sleep(2)
    bot_functions.press_down_keys(4)
    bot_functions.ClickImageOnScreen("./Screenshots/grid.png",1)
    time.sleep(3)
    bot_functions.press_tab_key(5) 
    pyautogui.press('enter')
    time.sleep(1)
    bot_functions.press_left_keys(5)

async def normalize_screen_to_scrape_comments(driver):
    view_replies_xpath = "//span[contains(text(), 'View replies')]"

    plus_counter = 0

    try:
        while True:
            # Try clicking "View replies" up to 10 times
            for _ in range(10):
                try:
                    element = await driver.find_element(By.XPATH, view_replies_xpath)
                    if element:
                        await element.click()
                        await asyncio.sleep(1)
                except Exception as e:
                    print(f"Exception found {e}")
                    # If not found, continue to next iteration
                    continue

            await asyncio.sleep(2)
            bot_functions.press_down_keys(45) 

            # Check for the plus.png image
            if bot_functions.LocateImageOnScreen('./Screenshots/plus.png'):
                bot_functions.ClickImageOnScreen('./Screenshots/plus.png', 1)
                await asyncio.sleep(2)
                pyautogui.moveTo(10,10)
                await asyncio.sleep(2)

                plus_counter += 1
                print("Clicked on more comments button ...")

            else:
                # If image not found, break out of the while loop
                break

            if plus_counter > 7: 
                break

    except Exception as e:
        print(e)

def scroller(scrolling_limit):

    """
    This function is used to scroll the followers modal ..
    """

    if bot_functions.LocateImageOnScreen('./Screenshots/search.png'):

        bot_functions.ClickImageOnScreen('./Screenshots/search.png', 1)
        time.sleep(7)

        pyautogui.press('tab')
        pyautogui.press('tab')
        pyautogui.press('tab')
        time.sleep(1)

        for _ in range(0, scrolling_limit):
            bot_functions.press_down_keys(75)
            time.sleep(0.5)
    
    else: 
        print("Search image not found ...")

def scrape_followers_list(html_content):
    """
    Finds all <div> tags, extracts href from <a> tags inside, and writes full Instagram profile URLs to usernames.txt.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    urls = []

    # Find all <div> tags
    for div in soup.find_all('div'):
        # Find all <a> tags inside the div
        for a in div.find_all('a', href=True):
            href = a['href']
            # Only consider profile links (usually start with /username/)
            if href.startswith('/') and href.count('/') == 2 and not '/p/' in href:
                full_url = f"https://www.instagram.com{href}"
                urls.append(full_url)

    urls = list(set(urls))  # Remove duplicates

    # Write all URLs to usernames.txt
    with open('usernames.txt', 'w', encoding='utf-8') as f:
        for url in urls:
            f.write(url + '\n')

# ============================================================
# METHODS required for mutiple processing of the instagram profiles ...
# ============================================================

def extract_phone_numbers(text):
    # Define a regex pattern for phone numbers
    phone_number_pattern = r"""
    (?<!\d)                   # Ensure no digit precedes the number (boundary check)
    (?:\+\d{1,3}\s?)?       # Optional country code with '+' (e.g., +1, +92)
    (?:\(?\d{2,4}\)?\s?-?)? # Optional area code with parentheses or hyphen (e.g., (203), 203-)
    \d{3,4}                   # First part of the phone number (3-4 digits)
    [-\s]?                    # Optional separator (space or hyphen)
    \d{3,4}                   # Second part of the phone number (3-4 digits)
    (?:[-\s]?\d{1,4})?       # Optional third part (1-4 digits for extended formats)
    (?!\d)                    # Ensure no digit follows the number (boundary check)
    """.strip()

    # Compile the regex with the VERBOSE flag for readability
    phone_number_regex = re.compile(phone_number_pattern, re.VERBOSE)

    # Find all matching phone numbers in the text
    phone_numbers = phone_number_regex.findall(text)

    if len(phone_numbers) > 0:
        return ", ".join(phone_numbers)

    else:
        return None


def extract_emails(text):
    # Define a regex pattern for email addresses
    email_pattern = r"""
    [a-zA-Z0-9._%+-]+          # Username: letters, digits, and valid special characters
    @                          # Literal '@'
    [a-zA-Z0-9.-]+            # Domain: letters, digits, dots, and hyphens
    \.[a-zA-Z]{2,}            # Top-level domain: at least 2 characters
    (?!\.[a-zA-Z]{2,}$)      # Exclude long invalid paths like '.jpg', '.png'
    """.strip()

    # Compile the regex with the VERBOSE flag for readability
    email_regex = re.compile(email_pattern, re.VERBOSE)

    # Find all matching email addresses in the text
    emails = email_regex.findall(text)

     # Filter emails: remove those with unwanted extensions or exceeding length
    filtered_emails = [email for email in emails 
                       if not email.endswith(('.jpg', '.png', '.gif', '.webp','.jpeg')) and len(email) <= 40]


    if len(filtered_emails) > 0:
        return ", ".join(filtered_emails)

    else:
        return None


def extract_meta_data_from_html(html_content):
    """
    Extract information from <meta> tags in HTML content.

    Args:
        html_content (str): The HTML content containing <meta> tags.

    Returns:
        dict: A dictionary containing the extracted information.
    """
    # Parse the HTML content using BeautifulSoup
    soup = BeautifulSoup(html_content, 'html.parser')

    # Find the <meta> tag with the attribute name="description"
    meta_tag = soup.find('meta', attrs={'name': 'description'})
    # print(meta_tag)

    if not meta_tag or not meta_tag.get('content'):
        return {}

    # Extract the content attribute
    meta_tag_content = meta_tag['content'] 

    # Regular expression pattern
    # pattern = r'\b[Pp]osts\b|\b[Ff]ollowers\b|\b[Ff]ollowing\b|@\w+'  
    # pattern = r'\d{1,3}(?:,\d{3})*(?:\.\d+)?(?:[MmKk])? followers|\b[Pp]osts\b|\b[Ff]ollowers\b|\b[Ff]ollowing\b|@\w+'

    pattern1 = r'\d{1,3}(?:,\d{3})*(?:\.\d+)?[MK]? [Ff]ollowers'
    pattern2 = r'\d{1,3}(?:,\d{3})?(?:[BbMmKk])? [Pp]osts'
    pattern3 = r'\d{1,3}(?:,\d{3})?(?:[BbMmKk])? [Ff]ollowing'

    # Finding all matches
    followers = re.findall(pattern1, meta_tag_content)[0]
    posts = re.findall(pattern2, meta_tag_content)[0]
    following = re.findall(pattern3, meta_tag_content)[0]

    username_and_description = meta_tag_content.split("on Instagram:")
    # print(username_and_description[0])

    username_pattern = r'@[\w_]+' 
    usernames = re.findall(username_pattern, username_and_description[0]) 
    description = username_and_description[1].strip() 

    phone_numbers = extract_phone_numbers(meta_tag_content)
    emails = extract_emails(meta_tag_content)

    if len(description) < 5: 
        description = None

    if len( usernames ) > 0:

        data = {
        '@username' : usernames[0], 
        'Posts' : posts,
        'Followers' : followers,
        'Following' : following,
        'Email' : emails,
        'Phone Number' : phone_numbers,
        'Description' : description, 
        'Profile Link' : f"https://www.instagram.com/{usernames[0].replace("@","")}"
        } 
    
    else: 

        data = None

    return data

def read_links_from_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        return [line.strip() for line in file if line.strip()]

# Function to divide the URL list into chunks
def divide_urls(url_list, num_chunks):
    chunk_size = ceil(len(url_list) / num_chunks)
    return [url_list[i:i + chunk_size] for i in range(0, len(url_list), chunk_size)]

# Wrapper for running the async scraper in a process
def scraper_wrapper(url_list):
    asyncio.run(async_scraper(url_list))

async def async_scraper(url_list):

    options = webdriver.ChromeOptions() 
    options.add_argument('--headless')  # Run in headless mode
    # options.add_argument('--icognito')  # Run in headless mode
    # print("Starting the asynchronous scraper... with headless mode enabled")

    async with webdriver.Chrome(options=options) as browser:
        for url in url_list:
            try:
                # Open the target website
                await browser.get(url,wait_load=False)
                await asyncio.sleep(5)  # Wait for the page to load 

                # Extract the page's HTML
                html_content = await browser.page_source 

                data = extract_meta_data_from_html(html_content) 
                data_store.store_to_json(data,'data.json')

                write_logs_to_file("-----------------Data Scraped-----------------")
                print("-------------------")
                for key, value in data.items():
                    print(f"{key}: {value}")
                    write_logs_to_file(f"{key}: {value}") 
                print("-------------------")
                write_logs_to_file("-------------------")
    
            except Exception as e:
                print(f"Error scraping {url}: {e}")

async def scrape_follower_info_using_async():

    """
    This function will initiate the multi-processed scraping task to extract the followers of certain profiles..
    """

    list_ = read_links_from_file('usernames.txt')

    # print("The total number of urls found are ",len(list_))

    # Divide URLs into 5 chunks
    num_processes = 5
    url_chunks = divide_urls(list_, num_processes)

    # print("The number of chunks created are ",len(url_chunks))

    # Use multiprocessing to run the scraper concurrently
    with Pool(num_processes, initializer=_child_redirect_init) as pool:
        pool.map(scraper_wrapper, url_chunks)

async def scrap_instagram_profile_public_followers_data(profile_url,scrolling_limit): 

    load_dotenv()
    username = os.getenv("INSTAGRAM_USERNAME")
    password = os.getenv("INSTAGRAM_PASSWORD")

    options = webdriver.ChromeOptions()
    options.add_argument("--incognito")

    async with webdriver.Chrome(options=options) as driver:

        try: 
            await login_to_instagram(driver,username,password)
            await driver.get(to_english_instagram_url(profile_url)) 
            await asyncio.sleep(5)  # Wait for the page to load 

            # click on a followers button ... 
            # XPath to find the followers button by its text
            followers_button_xpath = "//span[contains(text(), 'followers')]/ancestor::button | //span[contains(text(), 'followers')]"

            # Usage example:
            followers_button = await driver.find_element(By.XPATH, followers_button_xpath)
            await followers_button.click()

            await asyncio.sleep(5)  # Wait for the followers modal to load
            scroller(scrolling_limit)  # Scroll the followers modal to load more followers
            html_content = await driver.page_source 
            scrape_followers_list(html_content)

        except Exception as e: 
            print(f"The exception found is {e}")
    
    # if the usernames.txt contains some usernames then only proceed to scrape the profile information ...
    if os.path.exists('usernames.txt') and os.path.getsize('usernames.txt') > 0:
        # print("File found if block executed ...")
        await scrape_follower_info_using_async()
        data_store.save_data_to_excel('data.json','profile_followers_data.xlsx') 
        data_store.excel_to_json('profile_followers_data.xlsx','profile_followers_data.json')
        os.remove('usernames.txt')


async def click_on_any_xpath(driver, xpath_list):
    """
    Try to click elements from a list of XPaths.
    Breaks the loop when an element is successfully clicked.
    """



    for xpath in xpath_list:
        try:
            element = await driver.find_element(By.XPATH, xpath)
            await element.click()
            print(f"✅ Clicked on element using XPath: {xpath}")
            return True   # stop after success
        except Exception as e:
            print(f"❌ XPath not found/click failed: {xpath} - {e}")
            continue
    print("⚠️ No valid XPath found to click.")
    return False


async def send_bulk_messages_to_followers(followers_list,messages_list,total_messages_to_send,message_send_time_gap):

    """
    This function is used to send bulk messages to the followers of a certain profile. 
    It will read a message randomly from the messages_list and send it to the followers in the followers_list. 
    :param followers_list: List of followers to send messages to.
    """

    load_dotenv()
    username = os.getenv("INSTAGRAM_USERNAME")  
    password = os.getenv("INSTAGRAM_PASSWORD")

    options = webdriver.ChromeOptions()
    options.add_argument("--incognito")

    counter = 0
    
    async with webdriver.Chrome(options=options) as driver:
        try:

            await login_to_instagram(driver,username,password)

            for follower in followers_list: 

                await driver.get(follower)
                await asyncio.sleep(3) 

                
                

                try:

                    # Click on a auto follow button ... using Xpath 

                    FOLLOW_BUTTON_XPATHS = [
                   # Text-based (recommended)
                    "//div[normalize-space()='Follow']/ancestor::button[1]",
                    "//button[.//div[normalize-space()='Follow']]",
                    "//button[descendant::div[@dir='auto' and normalize-space()='Follow']]",
                    "(//button[.//div[normalize-space()='Follow']])[1]",

                    # Case-insensitive text variants
                    "//button[.//div[translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')='follow']]",
                    "//div[translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')='follow']/ancestor::button[1]",

                    # Class-anchored (less stable — IG classes often change)
                    "//button[contains(@class,'_aswp') and .//div[normalize-space()='Follow']]",
                    "//button[contains(@class,'_asx2') and .//div[normalize-space()='Follow']]",
                    "//button[.//div[contains(@class,'_ap3a') and normalize-space()='Follow']]",
                    "//div[contains(@class,'_ap3a') and normalize-space()='Follow']/ancestor::button[1]",

                    # Generic descendant text fallback
                    "//button[descendant::text()[normalize-space()='Follow']]",
                    ]

                    if random.choice([1,2,3,4,5,6,7,8,9,10]) > 5:

                        result = await click_on_any_xpath(driver,FOLLOW_BUTTON_XPATHS)

                        if result:
                            await asyncio.sleep(3) 


                    if bot_functions.LocateImageOnScreen('./Screenshots/message.png'):

                        bot_functions.ClickImageOnScreen('./Screenshots/message.png', 1)
                        time.sleep(8)
                        message_to_send = random.choice(messages_list) 
                        pyautogui.write(message_to_send)
                        time.sleep(2) 
                        pyautogui.press('enter') 

                        # for _ in range(0,50): 
                            # pyautogui.press('backspace')

                        counter += 1

                        pyautogui.press('esc')
                        time.sleep(message_send_time_gap)

                except Exception as e:
                    print(f"Exception found {e}")
                    continue

                if counter == total_messages_to_send:
                    break 
                
        except Exception as e:

            print(f"{e}")    

async def scrap_instagram_posts(comment_scraping_flag,instagram_profile_url,total_posts_to_scrap): 

    """
    This function is used to scrap the comments and profiles of the posts from Instagram.
    :param comment_scraping_flag: Boolean flag to indicate whether to scrape comments or not. 
    # by default it is set to False. 
    """

    load_dotenv()
    username = os.getenv("INSTAGRAM_USERNAME")  
    password = os.getenv("INSTAGRAM_PASSWORD")

    options = webdriver.ChromeOptions()
    options.add_argument("--incognito")
    
    async with webdriver.Chrome(options=options) as driver:
        try:

            await login_to_instagram(driver,username,password)

            counter = 0
            await driver.get(instagram_profile_url)
            await asyncio.sleep(3)  # Wait for the page to load
            move_to_first_post()

            if comment_scraping_flag == True:

                while(True): 

                    # a logic to extract the comments ... 
                    # await switch_to_latest_post(driver)
                    
                    await normalize_screen_to_scrape_comments(driver)
                    await asyncio.sleep(2)
                    current_url = await driver.current_url
                    html_content = await driver.page_source 

                    comments_data =  extract_comments_data(html_content,current_url)
                    data_store.append_dict_to_json(comments_data,'data.json')
                    print(f"The scraped data is {comments_data}")

                    if counter == total_posts_to_scrap: 
                        break

                    else: 

                        pyautogui.press('right')
                        await asyncio.sleep(2)
                        counter += 1
                    
                    # print(f"the counter is {counter}")
                
                data_store.save_data_to_excel('comments_data.json','instagram_posts_comments.xlsx')
                data_store.excel_to_json('instagram_posts_comments.xlsx','instagram_posts_comments_data.json')

            else:
                while(True):

                    current_url = await driver.current_url
                    html_content = await driver.page_source
                    dictionary = scrap_caption_likes_and_post_time(html_content)
                    dictionary['post_url'] = current_url

                    # print("the scraped data is ",dictionary)
                    write_logs_to_file(f"the scraped data is {dictionary}")

                    data_store.store_to_json(dictionary,'posts_data.json')
                    write_logs_to_file(f"The data is successfully stored in posts_data.json")

                    if counter > total_posts_to_scrap:
                        # print("Break ...")
                        break 
                    else: 
                        pyautogui.press('right')
                        await asyncio.sleep(2)
                        counter += 1
                
                data_store.save_data_to_excel('posts_data.json','instagram_posts_with_likes.xlsx')
                data_store.excel_to_json('instagram_posts_with_likes.xlsx','data.json')
        
        except Exception as e:

            print(f"{e}")

def extract_account_link_from_html(html_content):
    """
    Extracts the Instagram account link from the given HTML content.
    Returns the full URL like 'https://www.instagram.com/username/?hl=en'
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    # Target the specific div class
    target_class = "html-div xdj266r x14z9mp xat24cr x1lziwak xexx8yu xyri2b x18d9i69 x1c1uobl x9f619 x5lhr3w xjbqb8w x78zum5 x15mokao x1ga7v0g x16uus16 xbiv7yw x1n2onr6 x1plvlek xryxfnj x1c4vz4f x2lah0s xdt5ytf xqjyukv x1qjc9v5 x1oa3qoh xl56j7k"
    div = soup.find("div", class_=target_class)
    if not div:
        return None
    # Find the first <a> tag with href starting with "/"
    a_tag = div.find("a", href=True)
    if a_tag and a_tag['href'].startswith('/'):
        # Remove query params except ?hl=en
        base_href = a_tag['href'].split('?')[0]
        username = base_href.strip('/').split('/')[0]
        url = f"https://www.instagram.com/{username}/?hl=en"
        return url
    return None

def extract_meta_data_from_html_with_keyword(html_content,url):
    """
    Extract information from <meta> tags in HTML content.

    Args:
        html_content (str): The HTML content containing <meta> tags.

    Returns:
        dict: A dictionary containing the extracted information.
    """
    # Parse the HTML content using BeautifulSoup
    soup = BeautifulSoup(html_content, 'html.parser')

    # Find the <meta> tag with the attribute name="description"
    meta_tag = soup.find('meta', attrs={'name': 'description'})
    # print(meta_tag)

    if not meta_tag or not meta_tag.get('content'):
        return {}

    # Extract the content attribute
    meta_tag_content = meta_tag['content'] 

    """
    followers = re.findall(pattern1, meta_tag_content)[0]
                ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^
    IndexError: list index out of range
    """

    # Regular expression pattern
    # pattern = r'\b[Pp]osts\b|\b[Ff]ollowers\b|\b[Ff]ollowing\b|@\w+'  
    # pattern = r'\d{1,3}(?:,\d{3})*(?:\.\d+)?(?:[MmKk])? followers|\b[Pp]osts\b|\b[Ff]ollowers\b|\b[Ff]ollowing\b|@\w+'

    pattern1 = r'\d{1,3}(?:,\d{3})*(?:\.\d+)?[MK]? [Ff]ollowers'
    pattern2 = r'\d{1,3}(?:,\d{3})?(?:[BbMmKk])? [Pp]osts'
    pattern3 = r'\d{1,3}(?:,\d{3})?(?:[BbMmKk])? [Ff]ollowing'

    # Finding all matches
    followers = re.findall(pattern1, meta_tag_content)[0]
    posts = re.findall(pattern2, meta_tag_content)[0]
    following = re.findall(pattern3, meta_tag_content)[0]

    username_and_description = meta_tag_content.split("on Instagram:")
    # print(username_and_description[0])

    username_pattern = r'@[\w_]+' 
    usernames = re.findall(username_pattern, username_and_description[0]) 
    description = username_and_description[1].strip() 

    phone_numbers = extract_phone_numbers(meta_tag_content)
    emails = extract_emails(meta_tag_content)

    if len(description) < 5: 
        description = None

    if len( usernames ) > 0:

        data = {
        '@username' : usernames[0], 
        'Posts' : posts,
        'Followers' : followers,
        'Following' : following,
        'Email' : emails,
        'Phone Number' : phone_numbers,
        'Description' : description, 
        'Profile Link' : f"https://www.instagram.com/{usernames[0].replace("@","")}", 
        'keyword' : search_keyword_in_file(url)
        } 
    
    else: 

        data = None
    return data

def search_keyword_in_file(url):
    """
    Searches for the keyword corresponding to the given URL in 'urls_with_keywords.xlsx'.
    Returns the keyword if found, else returns None.
    """
    try:
        df = pd.read_excel('urls_with_keywords.xlsx')
        # Normalize URLs for comparison (strip whitespace)
        match = df[df['link'].astype(str).str.strip() == str(url).strip()]
        if not match.empty:
            return match.iloc[0]['keyword']
        else:
            return None
        
    except Exception as e:
        print(f"Error searching keyword in file: {e}")
        return None


# if __name__ == "__main__":

    # Start the entire scraping flow from a single function
    # list_of_accounts = ["https://www.instagram.com/johncena/","https://www.instagram.com/hormozi/","https://www.instagram.com/therock/"]

    # comments_to_post_list=["Wow! This is a great post","This is the content we need on Instagram","Keep posting, keep sharing","Amazing_post", "Free Palestine", "Go with Palestine"]

    # login_accounts_dict = {
    # 'usernames_list' : ['infohub_69','infohub_69'],
    # 'passwords_list' : ['cyberflex123','cyberflex123']
    # }

    # followers_list = ['https://www.instagram.com/rosangela__marcondes/','https://www.instagram.com/cleberananiasramos/','https://www.instagram.com/evelisantos94/']


    # asyncio.run(write_comments_on_instagram_posts(login_accounts_dict,list_of_accounts,3,comments_to_post_list))
    # asyncio.run(scrap_instagram_profile_public_followers_data('https://www.instagram.com/alice.mori02',2))
    # asyncio.run(scrap_instagram_posts(comment_scraping_flag=False,instagram_profile_url='https://www.instagram.com/hormozi',total_posts_to_scrap=3))
    # asyncio.run(send_bulk_messages_to_followers(followers_list,comments_to_post_list,3,message_send_time_gap=35))  
    
    # ai_function.perform_sentiment_analysis() #AI FUNCTION CALL
    # data_store.save_data_to_excel('data.json','profile_followers_data.xlsx') 
    # data_store.excel_to_json('profile_followers_data.xlsx','profile_followers_data.json')
    # os.remove('usernames.txt')
    # list_ = read_links_from_file('links.txt')
    # asyncio.run(find_targeted_audience(list_))
