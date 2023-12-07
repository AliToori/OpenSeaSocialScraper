#!/usr/bin/env python3
"""
    *******************************************************************************************
    OpenSeaScraper:  OpenSea Profile Social Media Handle Scraper
    Author: Ali Toori, Python Developer, Bot Builder
    *******************************************************************************************
"""
import json
import logging.config
import os
import pickle
import random
from datetime import datetime
from multiprocessing import freeze_support
from pathlib import Path
from time import sleep
import concurrent.futures

import pandas as pd
import pyfiglet
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class OpenSeaBot:
    def __init__(self):
        self.PROJECT_ROOT = Path(os.path.abspath(os.path.dirname(__file__)))
        self.file_settings = str(self.PROJECT_ROOT / 'BotRes/Settings.json')
        self.file_profiles = self.PROJECT_ROOT / 'BotRes/Profiles.csv'
        self.OPENSEA_HOME_URL = "https://opensea.io/"
        self.settings = self.get_settings()
        self.client_secret_file_name = self.settings['settings']['ClientSecretFileName']
        self.spread_sheet = self.settings['settings']['SpreadSheet']
        self.work_sheet = self.settings['settings']['WorkSheet']
        self.file_client_secret = str(self.PROJECT_ROOT / f'BotRes/{self.client_secret_file_name}')
        self.LOGGER = self.get_logger()
        self.driver = None
        self.spreadsheet_auth = self.get_spreadsheet_auth(spread_sheet=self.spread_sheet)

    # Get self.LOGGER
    @staticmethod
    def get_logger():
        """
        Get logger file handler
        :return: LOGGER
        """
        logging.config.dictConfig({
            "version": 1,
            "disable_existing_loggers": False,
            'formatters': {
                'colored': {
                    '()': 'colorlog.ColoredFormatter',  # colored output
                    # --> %(log_color)s is very important, that's what colors the line
                    'format': '[%(asctime)s,%(lineno)s] %(log_color)s[%(message)s]',
                    'log_colors': {
                        'DEBUG': 'green',
                        'INFO': 'cyan',
                        'WARNING': 'yellow',
                        'ERROR': 'red',
                        'CRITICAL': 'bold_red',
                    },
                },
                'simple': {
                    'format': '[%(asctime)s,%(lineno)s] [%(message)s]',
                },
            },
            "handlers": {
                "console": {
                    "class": "colorlog.StreamHandler",
                    "level": "INFO",
                    "formatter": "colored",
                    "stream": "ext://sys.stdout"
                },
                "file": {
                    "class": "logging.handlers.RotatingFileHandler",
                    "level": "INFO",
                    "formatter": "simple",
                    "filename": "OpenSeaBot.log",
                    "maxBytes": 5 * 1024 * 1024,
                    "backupCount": 3
                },
            },
            "root": {"level": "INFO",
                     "handlers": ["console", "file"]
                     }
        })
        return logging.getLogger()

    @staticmethod
    def enable_cmd_colors():
        # Enables Windows New ANSI Support for Colored Printing on CMD
        from sys import platform
        if platform == "win32":
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)

    @staticmethod
    def banner():
        pyfiglet.print_figlet(text='____________ OpenSeaBot\n', colors='RED')
        print('Author: AliToori, Full-Stack Python Developer\n'
              'Website: https://boteaz.com\n'
              '************************************************************************')

    def get_settings(self):
        """
        Creates default or loads existing settings file.
        :return: settings
        """
        if os.path.isfile(self.file_settings):
            with open(self.file_settings, 'r') as f:
                settings = json.load(f)
            return settings
        settings = {"Settings": {
            "ThreadsCount": 5
        }}
        with open(self.file_settings, 'w') as f:
            json.dump(settings, f, indent=4)
        with open(self.file_settings, 'r') as f:
            settings = json.load(f)
        return settings

    # Get random user-agent
    def get_user_agent(self):
        file_uagents = self.PROJECT_ROOT / 'BotRes/user_agents.txt'
        with open(file_uagents) as f:
            content = f.readlines()
        u_agents_list = [x.strip() for x in content]
        return random.choice(u_agents_list)

    # Get random user-agent
    def get_proxy(self):
        file_proxies = self.PROJECT_ROOT / 'BotRes/proxies.txt'
        with open(file_proxies) as f:
            content = f.readlines()
        proxy_list = [x.strip() for x in content]
        proxy = random.choice(proxy_list)
        self.LOGGER.info(f'Proxy selected: {proxy}')
        return proxy

    # Get web driver
    def get_driver(self, proxy=False, headless=False):
        driver_bin = str(self.PROJECT_ROOT / "BotRes/bin/chromedriver.exe")
        service = Service(executable_path=driver_bin)
        options = webdriver.ChromeOptions()
        options.add_argument("--start-maximized")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-blink-features")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-gpu")
        options.add_argument("--dns-prefetch-disable")
        options.add_argument('--ignore-ssl-errors')
        options.add_argument('--ignore-certificate-errors')
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option('excludeSwitches', ['enable-logging'])
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        prefs = {"profile.default_content_setting_values.geolocation": 2,
                 "profile.managed_default_content_setting_values.images": 2}
        options.add_experimental_option("prefs", prefs)
        options.add_argument(F'--user-agent={self.get_user_agent()}')
        if proxy:
            options.add_argument(f"--proxy-server={self.get_proxy()}")
        if headless:
            options.add_argument('--headless')
        driver = webdriver.Chrome(service=service, options=options)
        return driver

    # Finish and quit browser
    def finish(self, driver):
        try:
            self.LOGGER.info(f'Closing browser')
            driver.close()
            driver.quit()
        except WebDriverException as exc:
            self.LOGGER.info(f'Issue while closing browser: {exc.args}')

    @staticmethod
    def wait_until_visible(driver, css_selector=None, element_id=None, name=None, class_name=None, tag_name=None, duration=10000, frequency=0.01):
        if css_selector:
            WebDriverWait(driver, duration, frequency).until(EC.visibility_of_element_located((By.CSS_SELECTOR, css_selector)))
        elif element_id:
            WebDriverWait(driver, duration, frequency).until(EC.visibility_of_element_located((By.ID, element_id)))
        elif name:
            WebDriverWait(driver, duration, frequency).until(EC.visibility_of_element_located((By.NAME, name)))
        elif class_name:
            WebDriverWait(driver, duration, frequency).until(
                EC.visibility_of_element_located((By.CLASS_NAME, class_name)))
        elif tag_name:
            WebDriverWait(driver, duration, frequency).until(EC.visibility_of_element_located((By.TAG_NAME, tag_name)))

    # Authenticate to the Google SpreadSheet
    def get_spreadsheet_auth(self, spread_sheet="OpenSeaProfiles"):
        self.LOGGER.info(f'Getting SpreadSheet: {spread_sheet}')
        scope = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/spreadsheets',
                 "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]
        credentials = ServiceAccountCredentials.from_json_keyfile_name(self.file_client_secret, scope)
        spreadsheet_auth = gspread.authorize(credentials)
        return spreadsheet_auth

    # Gets profiles from the SpreadSheet
    def get_profiles(self, spreadsheet_auth, spread_sheet, work_sheet="Profiles"):
        spreadsheet = spreadsheet_auth.open(spread_sheet)
        worksheet = spreadsheet.worksheet(work_sheet)
        df = pd.DataFrame(worksheet.get_all_records())
        return [profile["Profile"] for profile in df.iloc]

    # Updates Twitter handles in the SpreadSheet using Google Drive API
    def update_spreadsheet(self, df, spread_sheet, work_sheet="Profiles"):
        spreadsheet = self.spreadsheet_auth.open(spread_sheet)
        worksheet = spreadsheet.worksheet(work_sheet)
        df = df.applymap(str)
        # worksheet.resize(1)
        worksheet.update([df.columns.values.tolist()] + df.values.tolist())
        # worksheet.append_rows(values=df.iloc[:].values.tolist())
        self.LOGGER.info(f'Updated SpreadSheet: {spread_sheet}: WorkSheet: {work_sheet}')

    def get_profile_handles(self, profiles):
        url_filter = '?search[sortBy]=UNIT_PRICE&search[sortAscending]=false'
        driver = self.get_driver()
        for i, profile in enumerate(profiles):
            # final_url = self.OPENSEA_HOME_URL + profile
            self.LOGGER.info(f"Scraping social media handle of profile {i}: {profile}")
            driver.get(profile)
            # Wait for the profile to load
            try:
                self.LOGGER.info(f"Waiting profile")
                self.wait_until_visible(driver=driver, css_selector='[data-testid="phoenix-header"]', duration=10)
            except:
                return
            twitter_handle = ''

            # Get Twitter handle
            self.LOGGER.info(f"Waiting Twitter handle")
            self.wait_until_visible(driver=driver, css_selector='[rel="nofollow noopener"]', duration=10)

            # Loop through all the profiles handles
            for profile_handle in driver.find_elements(By.CSS_SELECTOR, '[rel="nofollow noopener"]'):
                self.LOGGER.info(f"Handles: {profile_handle}")
                # Verify if twitter.com is in the href
                if 'twitter.com' in profile_handle.get_attribute('href'):
                    twitter_handle = profile_handle.get_attribute('href')
                    self.LOGGER.info(f"Twitter handle found: {twitter_handle}")
                else:
                    self.LOGGER.info(f"No Twitter handle found")

            profile_dict = {"Profile": profile, "TwitterHandle": twitter_handle}
            self.LOGGER.info(f'Profile: {str(profile_dict)}')
            # df = pd.DataFrame([profile_dict])
            df = pd.read_csv(self.file_profiles, index_col=None)
            # self.update_spreadsheet(df=df, spread_sheet=self.spread_sheet, work_sheet=self.work_sheet)
            # Update Twitter handle of the profile
            df.loc[df.Profile == profile, "TwitterHandle"] = twitter_handle
            df.to_csv(self.file_profiles, index=False)
            # if file does not exist write headers
            # if not os.path.isfile(self.file_profiles):
            #     df.to_csv(self.file_profiles, index=False)
            # else:  # else if exists so append without writing the header
            #     df.to_csv(self.file_profiles, mode='a', header=False, index=False)
            self.LOGGER.info(f"Stats have been saved to {self.file_profiles}")
            self.finish(driver=driver)

    def main(self):
        freeze_support()
        self.enable_cmd_colors()
        self.banner()
        self.LOGGER.info(f'OpenSeaBot launched')
        thread_counts = self.settings["settings"]["ThreadCount"]
        profiles = pd.read_csv(self.file_profiles, index_col=None)
        profiles = [profiles["Profile"] for profiles in profiles.iloc]
        self.get_profile_handles(profiles)
        # chunk = round(len(profiles) / thread_counts)
        # profile_chunks = [profiles[x:x + chunk] for x in range(len(profiles))]
        # with concurrent.futures.ThreadPoolExecutor(max_workers=thread_counts) as executor:
        #     executor.map(self.get_profile_handles, profile_chunks)
        # self.LOGGER.info(f'Process completed successfully!')


if __name__ == '__main__':
    OpenSeaBot().main()
