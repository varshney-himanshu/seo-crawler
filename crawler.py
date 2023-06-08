import requests
import json
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from urllib import robotparser
import os
import re
import ssl
import socket
import time
import xml.etree.ElementTree as ET

seo_data = {}
page_insights_key = "<page insight key>"

def crawl_website(base_url, delay=1):
    """
    Crawls a website and returns a set of all visited URLs.

    Args:
        base_url (str): The base URL of the website to crawl.
        delay (int): The delay in seconds between each request. Default is 1 second.

    Returns:
        set: A set of all visited URLs.
    """


    print("Crawling " + base_url)

    visited_urls = set()

    ignore_extensions = ('.pdf', '.doc', '.docx', '.xls', '.xlsx', '.jpg', '.jpeg', '.png', '.gif')

    ignore_chars = ('#', '?', "/#")

    urls_queue = [base_url]

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36 Edge/16.16299",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "max-age=0",
        "TE": "Trailers",
        'Referer': 'https://www.google.com/',
    }

    while urls_queue:
        url = urls_queue.pop(0)

        if url in visited_urls:
            continue

        visited_urls.add(url)
        print("- Processing: "+ url)

        try:
            response = requests.get(url)
            if response.status_code >= 500: 
                seo_data[url] = {"5xx_error_code": response.status_code, "4xx_error_code": None }
         
            

            if response.status_code >= 400: 
                seo_data[url] = {"5xx_error_code": None, "4xx_error_code": response.status_code }
            
        except:
            time.sleep(delay)
            continue

        parsed_html = BeautifulSoup(response.text, 'html.parser')

        page_analysis = analyze_page(url, parsed_html, base_url)
        seo_data[url] = page_analysis

        links = parsed_html.find_all('a')

        # print(f"-- {len(links)} links found adding to the queue")

        for link in links:
            href = link.get('href')
            # print(f"*** {href}")

            if href and urlparse(href).netloc == urlparse(base_url).netloc and not href.endswith(ignore_extensions):
                for char in ignore_chars:
                    href = href.split(char)[0]

                urls_queue.append(href)
            
            else: 
                if href and not href.startswith('http') and href.startswith("/"):
                    for char in ignore_chars:
                       href = href.split(char)[0]
                   
                    # print(f"found relative link: {href}")
                    href = urljoin(base_url, href)
                    if href and href not in visited_urls:
                        urls_queue.append(href)
        
        time.sleep(delay)
                
    return visited_urls

def analyze_page(url, parsed_html, base_url):
    
    if parsed_html.title is None:
        return None
    
    page_data = {}

    page_data["5xx_error"] = None
    page_data["4xx_error"] = None

    if url == base_url: 
        print(" -- getting desktop performace score")
        page_data["performance_score_desktop"] = get_desktop_score(url)
        print(" -- getting mobile performace score")
        page_data["performance_score_mobile"] = get_mobile_score(url)

        print(" -- getting alexa rank ")
        page_data["alexa_rank"] = get_alexa_rank(url)

        print(" -- getting domain age")
        page_data["domain_age"] = get_domain_age(url)

        ssl_valid = check_ssl(url)  
        page_data["ssl_valid"] = ssl_valid

        robots_txt_link = check_robots_txt(url)
        page_data["robots_txt_exist"] = False if robots_txt_link == False else True
        if page_data["robots_txt_exist"]:
            page_data["robots_txt_link"] = robots_txt_link
        else: 
            page_data["robots_txt_link"] = None

        page_data["robots_txt_valid"] = not check_if_robots_txt_has_errors(url)

        sitemap_link = check_sitemap(url)
        page_data["sitemap_exist"] = False if sitemap_link == False else True
        if page_data["sitemap_exist"]:
            page_data["sitemap_link"] = sitemap_link
        else: 
            page_data["sitemap_link"] = None
        
        page_data["sitemap_valid"] = not check_if_sitemap_xml_has_errors(url)
        page_data["sitemap_invalid_links"] = crawl_sitemap_for_invalid_links(sitemap_link)


    # Title analysis
    title = parsed_html.title.string.strip() if parsed_html.title.string else ""
    page_data['title'] = title

    # Meta description analysis
    meta_desc = parsed_html.find('meta', attrs={'name': 'description'})
    if meta_desc:
        desc = meta_desc.get('content', '').strip()
        page_data['description'] = desc

  
    # Header analysis
    headers = parsed_html.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
    if headers:
        page_data['h1'] = []
        page_data['h2'] = []
        page_data['h3'] = []
        page_data['h4'] = []
        page_data['h5'] = []
        page_data['h6'] = []
        for header in headers:
            header_level = int(header.name[1])
            header_text = header.get_text().strip()
            page_data[f'h{header_level}'].append(header_text)
        

    # Keyword analysis
    keyword_meta = parsed_html.find('meta', attrs={'name': 'keywords'})
    if keyword_meta:
        keywords = keyword_meta.get('content', '').strip()
        page_data['keywords'] = keywords

    # Image analysis
    images = parsed_html.find_all('img')
    if images:
        image_count = len(images)
        alt_count = 0
        missing_alt_count = 0

        for image in images:
            if 'alt' in image.attrs:
                alt_count += 1
            else:
                missing_alt_count += 1

        page_data['image_count'] = image_count
        page_data['alt_count'] = alt_count
        page_data['missing_alt_count'] = missing_alt_count

    # Link analysis
    internal_links = []
    external_links = []
    links = parsed_html.find_all('a')
    for link in links:
        href = link.get('href')
        if href:
            if urlparse(href).netloc == urlparse(url).netloc:
                internal_links.append(href)
            else:
                external_links.append(href)

    if links:
        link_count = len(links)
        internal_link_count = 0
        external_link_count = 0
        missing_link_count = 0

        for link in links:
            href = link.get('href')
            if href:
                if urlparse(href).netloc == urlparse(url).netloc:
                    internal_link_count += 1
                else:
                    external_link_count += 1
            else:
                missing_link_count += 1

        page_data['link_count'] = link_count
        page_data['internal_link_count'] = internal_link_count
        page_data['external_link_count'] = external_link_count
        page_data['missing_link_count'] = missing_link_count

    # Word count analysis
    text = parsed_html.get_text()
    word_count = len(text.split())
    page_data['word_count'] = word_count

    # Mobile friendly analysis
    mobile_friendly = parsed_html.find('meta', attrs={'name': 'viewport'}) is not None
    page_data['mobile_friendly'] = mobile_friendly

    # Page speed analysis
    speed = requests.get(f'https://developers.google.com/speed/pagespeed/insights/?url={url}').url
    page_data['speed'] = speed

    # Canonical URL analysis
    canonical_link = parsed_html.find('link', attrs={'rel': 'canonical'})
    if canonical_link:
        canonical_url = canonical_link.get('href', '').strip()
        page_data['canonical_url'] = canonical_url
    else: 
        page_data['canonical_url'] = None
    
    #Structured data analysis
    structured_data = parsed_html.find_all('script', attrs={'type': 'application/ld+json'})
    if structured_data:
        page_data['structured_data'] = []
        for data in structured_data:
            page_data['structured_data'].append(data.get_text().strip())
    else: 
        page_data['structured_data'] = None

    #Social Media meta tags analysis
    social_meta = parsed_html.find_all('meta', attrs={'property': re.compile(r'^og:')})
    if social_meta:
        page_data['social_meta'] = {}
        for meta in social_meta:
            property_name = meta.get('property', '').strip()[3:]
            property_content = meta.get('content', '').strip()
            page_data['social_meta'][property_name] = property_content
    else:
        page_data['social_meta'] = None

    # Twitter meta tag analysis
    twitter_meta = parsed_html.find_all('meta', attrs={'name': lambda name: name and name.startswith('twitter:')})
    if twitter_meta:
        twitter_dict = {}
        for tag in twitter_meta:
            property_name = tag['name'][8:]
            property_value = tag['content']
            twitter_dict[property_name] = property_value
        page_data['twitter_meta'] = twitter_dict
    else: 
        page_data['twitter_meta'] = None

    return page_data

def get_alexa_rank(url):
    """
    Returns the Alexa Rank of the provided URL
    """
    try:
        response = requests.get(f"https://data.alexa.com/data?cli=10&url={url}")
        soup = BeautifulSoup(response.text, "lxml")
        rank = soup.find("reach")['rank']
        return int(rank)
    except:
        return None

def get_domain_age(url):
    """
    Returns the age of the domain in years
    """
    domain_name = urlparse(url).netloc
    try:
        creation_date = whois.whois(domain_name).creation_date
        if type(creation_date) == list:
            creation_date = creation_date[0]
        age = (datetime.datetime.now() - creation_date).days // 365
        return age
    except:
        return None


def get_mobile_score(url):
    """
    Returns the mobile page speed score for a given url using Google's PageSpeed Insights API.
    """
    api_key = page_insights_key
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'}
    endpoint = 'https://www.googleapis.com/pagespeedonline/v5/runPagespeed'
    params = {
        'url': url,
        'strategy': 'mobile',
        'key': api_key
    }
    response = requests.get(endpoint, headers=headers, params=params)
    data = response.json()
    score = data['lighthouseResult']['categories']['performance']['score'] * 100
    return score

def check_if_robots_txt_has_errors(url):
    rp = robotparser.RobotFileParser()
    rp.set_url(url + "/robots.txt")
    try:
        rp.read()
        return False
    except:
        print("have errors")
        return True


def check_robots_txt(url):
    try:
        response = requests.get(f"{url}/robots.txt")
        if response.status_code == 200:
            return f"{url}/robots.txt"
        else:
            return False
    except:
        return False


def get_desktop_score(url):
    """
    Returns the desktop page speed score for a given url using Google's PageSpeed Insights API.
    """
    api_key = page_insights_key
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'}
    endpoint = 'https://www.googleapis.com/pagespeedonline/v5/runPagespeed'
    params = {
        'url': url,
        'strategy': 'desktop',
        'key': api_key
    }
    response = requests.get(endpoint, headers=headers, params=params)
    data = response.json()
    score = data['lighthouseResult']['categories']['performance']['score'] * 100
    return score



def check_ssl(url):
    hostname = url.split('//')[-1].split('/')[0]
    port = 443

    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE

    try:
        with socket.create_connection((hostname, port)) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                return True
    except:
        return False

def crawl_sitemap_for_invalid_links(url):
    """
    Crawls a sitemap XML file and checks for invalid links
    Returns a list of URLs that returned a 4xx or 5xx HTTP status code
    """
    try:
        response = requests.get(url)
        if response.status_code != 200:
            return None
        root = ET.fromstring(response.content)
        urls = []
        for child in root:
            if 'sitemap' in child.tag:
                sitemap_url = child[0].text
                sitemap_urls = crawl_sitemap_xml(sitemap_url)
                if sitemap_urls:
                    urls += sitemap_urls
            else:
                url = child[0].text
                response = requests.get(url)
                if response.status_code >= 400:
                    urls.append(url)
        return urls
    except:
        return None

def check_sitemap(url):
    try:
        response = requests.get(f"{url}/sitemap.xml")
        if response.status_code == 200:
            return f"{url}/sitemap.xml"
        else:
            return False
    except:
        return False

def check_if_sitemap_xml_has_errors(url):
    """
    Checks if the sitemap.xml file at the given URL exists and has valid XML format
    Returns True if the sitemap.xml file exists and has valid format, False otherwise
    """
    try:
        sitemap_url = f"{url.rstrip('/')}/sitemap.xml"
        response = requests.get(sitemap_url)
        
        if response.status_code == 200:
            # Parse the XML response
            root = ET.fromstring(response.content)
            return False
        else:
            return True
    except:
        return True

def save_visited_urls(visited_urls, output_folder):
    """
    Saves the set of visited URLs to a JSON file in the specified output folder.

    Args:
        visited_urls (set): The set of visited URLs.
        output_folder (str): The path of the folder to save the output file in.
    """
    hostname = urlparse(list(visited_urls)[0]).hostname.split(".")[0]
    file_name = f"{hostname}.json"

    data = {'urls': list(visited_urls), "seo_data": seo_data}

    try:
        os.makedirs(output_folder, exist_ok=True)
    except OSError as error:
        if error.errno == 17:
            print(error)
        else:
            raise

    with open(os.path.join(output_folder, file_name), 'w') as f:
        json.dump(data, f, indent=4)


if __name__ == '__main__':
    base_url = input("Enter the base URL of the website to crawl: ")

    visited_urls = crawl_website(base_url)

    output_folder = "json-output"
    save_visited_urls(visited_urls, output_folder)
