import re
import logging
from datetime import datetime, timedelta

from scrapy import Request
from city_scrapers_core.constants import BOARD
from city_scrapers_core.items import Meeting
from city_scrapers_core.spiders import CityScrapersSpider


class CuyaElectionsSpider(CityScrapersSpider):
    name = "cuya_elections"
    agency = "Cuyahoga County Board of Elections"
    timezone = "America/Detroit"
    start_urls = ["https://boe.cuyahogacounty.gov/calendar"]
    location = {
        "name": "Board of Elections",
        "address": "2925 Euclid Ave, Cleveland, OH 44115",
    }
    document_url = "https://boe.cuyahogacounty.gov/about-us/board-meeting-documents"

    def parse(self, response):
        return self._fetch_documents(response)

    def _fetch_documents(self, response): 
        return Request(
            url=self.document_url,
            callback=self._parse_documents,
            cb_kwargs={
                'page_response': response
            })

    def _parse_documents(self, document_response, page_response):
        documents = {}
        content_section = document_response.css("section#Contentplaceholder1_TAA75111F019_Col00")
        dates = content_section.css("h3.heading-s")
        links = content_section.css("h3.heading-s + p")
        dates_and_links = zip(dates, links)
        for date, links in dates_and_links:
            key = date.css("::text").extract_first()
            raw_links = links.css("a")
            parsed_links = [{link.css("::text").extract_first().strip(): link.attrib["href"] } for link in raw_links]
            documents[key] = parsed_links

        logging.debug(documents)
        return self._parse_event_list(documents, page_response)

    def _parse_event_list(self, documents, response):
        event_list = response.css("ul.item-list li.item")
        for event in event_list:
            title = self._parse_title(event)
            if not('board' in title.lower()):
                continue
            yield self._fetch_event_details(event, documents, response.url)
    

    def _fetch_event_details(self, item, documents, url):
        details_url = item.css("h3.title a").attrib["href"]
        return Request(
            url=details_url,
            callback=self._parse_event_with_details,
            cb_kwargs={
                'item': item, 
                'url': url,
                'documents': documents, 
            })

    def _parse_event_with_details(self, details, item, url, documents):
        start, end = self._parse_start_end(item)
        meeting = Meeting(
            title=self._parse_title(item),
            description=self._parse_description(details),
            classification=BOARD,
            start=start,
            end=end,
            all_day=False,
            time_notes="",
            location=self._parse_location(details),
            links=[],
            source=url
        )

        meeting["status"] = self._get_status(meeting)
        meeting["id"] = self._get_id(meeting)
        
        yield meeting

    def _parse_title(self, item):
        return item.css("h3.title a::text").extract_first().strip()

    def _parse_start_end(self, item):
        """Parse start, end datetimes as naive datetime objects."""
        [month_str, day_str, year_str] = item.css("div.event span::text").extract()
        out_list = []
        for time_str in item.css("div.meta em::text").extract():
            date_time_str = f'{month_str} {day_str} {year_str} {time_str}'
            out_list.append(datetime.strptime(date_time_str, "%b %d %Y %I:%M %p"))
        end = None
        if len(out_list) > 1:
            end = out_list[1]
        return out_list[0], end

    def _parse_location(self, response):
        """Parse or generate location."""
        location = response.css("address *::text").extract_first()
        if (location):
            location = location.strip().replace("\r\n", "")
            return {
             "name": "Board of Elections",
             "address": "2925 Euclid Ave, Cleveland, OH 44115",
            }
        return self.location

    def _parse_description(self, response):
        """Parse or generate description"""
        main_description = response.css("div.related-content + p::text").extract()
        list_item_descriptions = response.css('div.related-content ~ ul li::text').extract()
        main_description_parsed = [description.strip() for description in main_description if ("About Us" not in description and "" != description.strip())]
        list_item_descriptions_parsed = [description.strip() for description in list_item_descriptions]
        
        description_str = " ".join(main_description_parsed + list_item_descriptions_parsed)
        return description_str

    # def parse(self, response):
    #     today = datetime.now()
    #     payload = {
    #         "ctl00$ctl00$ContentPlaceHolder1$ContentPlaceHolderMain$ctl00": "ctl00$ctl00$ContentPlaceHolder1$ContentPlaceHolderMain$EventsCalendar1$updMainPanel|ctl00$ctl00$ContentPlaceHolder1$ContentPlaceHolderMain$EventsCalendar1$TabContainer1$tbpDateRange$btnShowDateRange",  # noqa
    #         "__EVENTTARGET": "ctl00$ctl00$ContentPlaceHolder1$ContentPlaceHolderMain$EventsCalendar1$TabContainer1",  # noqa
    #         "__EVENTARGUMENT": "activeTabChanged:3",
    #         "__VIEWSTATE": response.css("#__VIEWSTATE::attr(value)").extract_first(),
    #         "__VIEWSTATEGENERATOR": response.css(
    #             "#__VIEWSTATEGENERATOR::attr(value)"
    #         ).extract_first(),
    #         "__EVENTVALIDATION": response.css(
    #             "#__EVENTVALIDATION::attr(value)"
    #         ).extract_first(),
    #         "__AjaxControlToolkitCalendarCssLoaded": "",
    #         "ctl00$ctl00$ContentPlaceHolder1$ContentPlaceHolderMain$EventsCalendar1$TabContainer1$tbpDateRange$txtStartDate": (  # noqa
    #             today - timedelta(days=200)
    #         ).strftime(
    #             "%m/%d/%Y"
    #         ),
    #         "ctl00$ctl00$ContentPlaceHolder1$ContentPlaceHolderMain$EventsCalendar1$TabContainer1$tbpDateRange$txtEndDate": (  # noqa
    #             today + timedelta(days=10)
    #         ).strftime(
    #             "%m/%d/%Y"
    #         ),
    #         "ContentPlaceHolder1_ContentPlaceHolderMain_EventsCalendar1_TabContainer1_ClientState": '{"ActiveTabIndex":3,"TabState":[true,true,true,true]}',  # noqa
    #     }
    #     yield FormRequest(
    #         response.url, formdata=payload, callback=self._parse_form_response
    #     )

    # def _parse_form_response(self, response):
    #     for link in response.css(".SearchResults td:nth-child(2) a"):
    #         link_text = " ".join(link.css("*::text").extract())
    #         # TODO: Include other notices?
    #         if "Board" not in link_text:
    #             continue
    #         yield response.follow(
    #             link.attrib["href"], callback=self._parse_detail, dont_filter=True
    #         )

    # def _parse_detail(self, response):
    #     """
    #     `_parse_detail` should always `yield` Meeting items.

    #     Change the `_parse_title`, `_parse_start`, etc methods to fit your scraping
    #     needs.
    #     """
    #     start, end = self._parse_start_end(response)
    #     meeting = Meeting(
    #         title=self._parse_title(response),
    #         description="",
    #         classification=BOARD,
    #         start=start,
    #         end=end,
    #         all_day=False,
    #         time_notes="",
    #         location=self._parse_location(response),
    #         links=self._parse_links(response),
    #         source=response.url,
    #     )

    #     meeting["status"] = self._get_status(
    #         meeting, text=" ".join(response.css(".padding *::text").extract())
    #     )
    #     meeting["id"] = self._get_id(meeting)

    #     yield meeting

    # def _parse_title(self, response):
    #     """Parse or generate meeting title."""
    #     title_str = " ".join(response.css(".padding h1 *::text").extract())
    #     if "Special" in title_str:
    #         return title_str
    #     return "Board of Elections"

    # def _parse_start_end(self, response):
    #     """Parse start, end datetimes as naive datetime objects."""
    #     dt_list = []
    #     for item_str in response.css(".padding dd::text").extract():
    #         dt_match = re.search(
    #             r"\d{1,2}/\d{1,2}/\d{4}-\d{1,2}:\d{2} [APM]{2}", item_str
    #         )
    #         if dt_match:
    #             dt_list.append(datetime.strptime(dt_match.group(), "%m/%d/%Y-%I:%M %p"))
    #     end = None
    #     if len(dt_list) > 1:
    #         end = dt_list[1]
    #     return dt_list[0], end


    # def _parse_links(self, response):
    #     """Parse or generate links."""
    #     links = []
    #     for link in response.css(".padding blockquote a"):
    #         link_title = " ".join(link.css("*::text").extract()).strip()
    #         links.append(
    #             {"title": link_title, "href": response.urljoin(link.attrib["href"])}
    #         )
    #     return links
