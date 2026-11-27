from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.keys import Keys


 
if __name__ == "__main__":
    s =Service('chromedriver.exe')
    driver = webdriver.Chrome(service=s)
    driver.get("https://www.python.org")
    assert "Python" in driver.title
    elem = driver.find_element_by_name("q")
    elem.send_keys("pycon")
    elem.send_keys(Keys.RETURN)
    driver.close()