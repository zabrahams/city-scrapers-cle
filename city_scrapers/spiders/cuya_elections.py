from datetime import datetime, timedelta

from scrapy import Request
from city_scrapers_core.constants import BOARD
from city_scrapers_core.items import Meeting
from city_scrapers_core.spiders import CityScrapersSpider


class CuyaElectionsSpider(CityScrapersSpider):
    name = "cuya_elections"
    agency = "Cuyahoga County Board of Elections"
    timezone = "America/Detroit"
    start_urls = [
        # We fetch past meetings from the first url and current/future ones
        # from the second
        "https://boe.cuyahogacounty.gov/calendar?sort=datedesc&it=Past%20Events&mpp=96",
        "https://boe.cuyahogacounty.gov/calendar?it=Current%20Events&mpp=96"
    ]
    location = {
        "name": "Board of Elections",
        "address": "2925 Euclid Ave, Cleveland, OH 44115",
    }
    document_url = "https://boe.cuyahogacounty.gov/about-us/board-meeting-documents"

    def parse(self, response):
        """
        This scraper is fairly complicated because the info for each meeting
        is distributed across three different places:
        (1) The calendar page (which needs to be fetched separately for future
            and past meetings)
        (2) The minutes/presentations are in the about us/board documents page
        (3) each meeting has a page including its description.
        Scrapy makes all its requests asynchronously and then continues the flow
        using callbacks, and this makes the flow a little convoluted.

        In order to do the scraping we start with two initial urls - one for the
        past meetings and one for current/future meetings. We then go through
        the following steps for each url:
        (i) Fetch the about us/board documents page (_fetch_documents)
        (ii) Parse it into a dictionary of dates to links which can be passed down
            (_parse_documents)
        (iii) Extract all the meetings from the main response (_parse_event_list)
        For each meeting we extracted we then:
        (iv) Fetch the meeting details from the meeting details page (_fetch_event_details)
        (v) Generate and yield the actual meeting (_parse_event_with_details)

        Going from fetching documents to parsing them, and from fetching meeting details
        to generating the meetings page both happen via callbacks on request objects.
        """
        return self._fetch_documents(response)

    def _fetch_documents(self, response): 
        """
        _fetch_documents grabs the about us/document page. The parsing of the
        results happens in the callback to _parse_documents. 
        """
        return Request(
            url=self.document_url,
            callback=self._parse_documents,
            cb_kwargs={
                'page_response': response
            })


    def _parse_documents(self, document_response, page_response):
        """
        _parse_documents and parses a response from fetching the document page
        into a dictionary of event date strings to lists of document links.
        Note that a few of the links on the page for meetings circa Nov 2020
        seem to be incorrect as of 2/1/2022. If you see weird results in the 
        scraper it might be because of errors on the page itself.
        """
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

        return self._parse_event_list(documents, page_response)

    def _parse_event_list(self, documents, response):
        """
        _parse_event_list pulls each event out of the primary response.
        It then iterates over them to parse individual events.
        """
        event_list = response.css("ul.item-list li.item")
        for event in event_list:
            title = self._parse_title(event)
            if not('board' in title.lower()):
                continue
            yield self._fetch_event_details(event, documents, response.url)
    

    def _fetch_event_details(self, item, documents, url):
        """
        _fetch_event_details fetches the page containing the events
        description and location.  It then passes control to
        _parse_event_with_details - the function that primarily generates
        the meeting - in the Request's callback.
        """
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
        """
        _parse_event_with_details generates and yields an individual meeting.
        """
        start, end = self._parse_start_end(item)
        documents_date_key = start.strftime('%m/%d/%Y')
        meeting = Meeting(
            title=self._parse_title(item),
            description=self._parse_description(details),
            classification=BOARD,
            start=start,
            end=end,
            all_day=False,
            time_notes="",
            links=[],
            location=self._parse_location(details),
            source=url
        )

        if documents_date_key in documents:
            meeting["links"] = documents[documents_date_key]

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