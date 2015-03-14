# -*- coding: utf-8 -*-
import requests
from bs4 import BeautifulSoup

from calibre import as_unicode
from calibre.utils.date import parse_only_date
from calibre.ebooks.metadata import check_isbn
from calibre.ebooks.metadata.book.base import Metadata
from calibre.ebooks.metadata.sources.base import Source


class BookradarMetadataSourcePlugin(Source):

    version = (0, 1, 0)

    author = 'Igor `idle sign` Starikov'

    name = 'Bookradar'
    description = 'Searches for books metadata on bookradar.org, well-suited for titles in Russian. \n' \
                  'Requires `requests` and `BeautifulSoup` packages to function.'

    capabilities = frozenset(('identify',))
    supported_platforms = ('windows', 'osx', 'linux')
    touched_fields = frozenset(('title', 'authors', 'identifier:isbn', 'publisher', 'pubdate'))
    cached_cover_url_is_reliable = False

    url_pattern = 'http://bookradar.org/search/?q=%s&type=all'

    @classmethod
    def find(cls, base_element, class_name, single=False):
        found = base_element.find_all('div', class_=class_name)
        if single:
            if not found:
                return ''
            return found[0].text.strip()
        return found

    @classmethod
    def parse_response(cls, response, isbn_initial, log):
        metadata_items = []

        page_soup = BeautifulSoup(response.text)

        for idx, candidate in enumerate(cls.find(page_soup, 'b-result'), 1):

            title = cls.find(candidate, 'b-result__name-wrap', True)
            author = map(unicode.strip, cls.find(candidate, 'b-result__author', True).split(','))
            comments = cls.find(candidate, 'b-result__desc__full', True).replace(u'Скрыть', '').strip()
            isbn = cls.find(candidate, 'b-result__isbn', True).split(':')[-1].split(',')[0].strip()

            log.info(u'Found candidate %s: %s' % (idx, title))

            publisher = None
            pubdate = None

            other_info = cls.find(candidate, 'b-result__years', True).strip()
            if other_info:
                for entry in other_info.split(';'):
                    k, v = entry.split(':', 1)
                    k = k.strip()
                    if k == u'Год':
                        pubdate = parse_only_date('1.1.%s' % v.split(',')[0].strip())
                    elif k == u'Издательство':
                        publisher = v.strip()

            metadata_item = Metadata(title, author)
            metadata_item.isbn = isbn or isbn_initial

            if comments:
                metadata_item.comments = comments

            if publisher is not None:
                metadata_item.publisher = publisher

            if pubdate is not None:
                metadata_item.pubdate = pubdate

            metadata_items.append(metadata_item)

        return metadata_items

    def is_customizable(self):
        return False

    def identify(self, log, result_queue, abort, title=None, authors=None, identifiers=None, timeout=30):
        log.debug(u'Bookradar identification started ...')

        identifiers = identifiers or {}
        search_tokens = []

        if title:
            search_tokens += list(self.get_title_tokens(title))

        if authors:
            search_tokens += list(self.get_author_tokens(authors, only_first_author=True))

        isbn = check_isbn(identifiers.get('isbn', None))
        if isbn:
            search_tokens += (isbn,)

        search_str = ' '.join(search_tokens)
        url = self.url_pattern % search_str

        log.info(u'Searching for: %s' % search_str)

        try:
            response = requests.get(url, timeout=timeout)
        except requests.exceptions.RequestException as e:
            log.exception('Failed to get data from `%s`: %s' % (url, e.message))
            return as_unicode(e)

        if abort.is_set():
            return

        metadata = self.parse_response(response, isbn_initial=isbn, log=log)

        for result in metadata:
            self.clean_downloaded_metadata(result)
            result_queue.put(result)


if __name__ == '__main__':
    # Tests
    # calibre-customize -b . && calibre-debug -e __init__.py

    from calibre.ebooks.metadata.sources.test import (test_identify_plugin, title_test, authors_test)

    test_identify_plugin(BookradarMetadataSourcePlugin.name, [
        (
            {'identifiers': {'isbn': '9785932861578'}},
            [
                title_test(u'Python. Подробный справочник', exact=True),
                authors_test([u'Дэвид Бизли'])
            ]
        ),
        (
            {
                'title': u'справочник',
                'identifiers': {'isbn': '9785932861578'}
            },
            [
                title_test(u'Python. Подробный справочник', exact=True),
                authors_test([u'Дэвид Бизли'])
            ]
        ),
        (
            {
                'title': u'Opencv Computer Vision',
                'authors': u'Howse'
            },
            [
                title_test(u'Opencv Computer Vision with Python', exact=True),
                authors_test([u'Joseph Howse'])
            ]
        ),
    ])
