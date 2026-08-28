from __future__ import annotations

import argparse

from seleniumbase import Driver
from selenium.webdriver.support.ui import WebDriverWait

from base.scraper import UrlScraper
from interfaces.iconfig import ICrawlerConfig
from logger import get_logger

import json

logger = get_logger(__name__)


class SeleniumBaseScraper(UrlScraper):
    def __init__(self, *, headless: bool = False, page_load_timeout: int = 30) -> None:
        self.headless = headless
        self.page_load_timeout = page_load_timeout

    def _build_driver_options(self, config: ICrawlerConfig):
        driver_options: dict[str, object] = {
            "uc": config.uc,
            "headless": self.headless or config.headless,
        }
        if config is not None and config.proxy:
            driver_options["proxy"] = config.proxy
        return driver_options

    def scrape(self, url: str, config: ICrawlerConfig | None = None) -> str:
        logger.info("Starting crawl: %s", url)
        request_timeout = (
            config.request_timeout if config is not None else self.page_load_timeout
        )

        driver = Driver(**self._build_driver_options(config))
        try:
            driver.set_page_load_timeout(request_timeout)
            driver.get(url)
            WebDriverWait(driver, request_timeout).until(
                lambda current_driver: current_driver.execute_script(
                    "return document.readyState"
                )
                == "complete"
            )
            logger.info("Finished crawl: %s", url)
            json_response = driver.execute_script("return window.App.cache")
            return json.dumps(json_response)

        except TypeError as ex:
            logger.exception("TypeError at scrape: {ex}")
            raise

        except Exception:
            logger.exception("Crawl failed: %s", url)
            raise
        finally:
            driver.quit()


def main() -> None:
    argument_parser = argparse.ArgumentParser(
        description="Fetch a Craft page with SeleniumBase UC mode."
    )
    argument_parser.add_argument("url", help="The page URL to fetch")
    argument_parser.add_argument(
        "--headless",
        action="store_true",
        help="Run Chrome without opening a visible browser window",
    )
    arguments = argument_parser.parse_args()

    html = SeleniumBaseScraper(headless=arguments.headless).scrape(arguments.url)
    print(html)


if __name__ == "__main__":
    main()
