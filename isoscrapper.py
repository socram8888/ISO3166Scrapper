#!/usr/bin/env python3

import json
import requests
import lxml.html
import re
import sys
import csv

COUNTRY_CODES = [
	'AF', 'AX', 'AL', 'DZ', 'AS', 'AD', 'AO', 'AI', 'AQ', 'AG', 'AR', 'AM', 'AW', 'AU', 'AT', 'AZ', 'BS', 'BH', 'BD', 'BB', 'BY', 'BE', 'BZ', 'BJ', 'BM', 'BT', 'BO', 'BQ', 'BA', 'BW', 'BV', 'BR', 'IO', 'BN', 'BG', 'BF', 'BI', 'KH', 'CM', 'CA', 'CV', 'KY', 'CF', 'TD', 'CL', 'CN', 'CX', 'CC', 'CO', 'KM', 'CG', 'CD', 'CK', 'CR', 'CI', 'HR', 'CU', 'CW', 'CY', 'CZ', 'DK', 'DJ', 'DM', 'DO', 'EC', 'EG', 'SV', 'GQ', 'ER', 'EE', 'ET', 'FK', 'FO', 'FJ', 'FI', 'FR', 'GF', 'PF', 'TF', 'GA', 'GM', 'GE', 'DE', 'GH', 'GI', 'GR', 'GL', 'GD', 'GP', 'GU', 'GT', 'GG', 'GN', 'GW', 'GY', 'HT', 'HM', 'VA', 'HN', 'HK', 'HU', 'IS', 'IN', 'ID', 'IR', 'IQ', 'IE', 'IM', 'IL', 'IT', 'JM', 'JP', 'JE', 'JO', 'KZ', 'KE', 'KI', 'KP', 'KR', 'KW', 'KG', 'LA', 'LV', 'LB', 'LS', 'LR', 'LY', 'LI', 'LT', 'LU', 'MO', 'MK', 'MG', 'MW', 'MY', 'MV', 'ML', 'MT', 'MH', 'MQ', 'MR', 'MU', 'YT', 'MX', 'FM', 'MD', 'MC', 'MN', 'ME', 'MS', 'MA', 'MZ', 'MM', 'NA', 'NR', 'NP', 'NL', 'NC', 'NZ', 'NI', 'NE', 'NG', 'NU', 'NF', 'MP', 'NO', 'OM', 'PK', 'PW', 'PS', 'PA', 'PG', 'PY', 'PE', 'PH', 'PN', 'PL', 'PT', 'PR', 'QA', 'RE', 'RO', 'RU', 'RW', 'BL', 'SH', 'KN', 'LC', 'MF', 'PM', 'VC', 'WS', 'SM', 'ST', 'SA', 'SN', 'RS', 'SC', 'SL', 'SG', 'SX', 'SK', 'SI', 'SB', 'SO', 'ZA', 'GS', 'SS', 'ES', 'LK', 'SD', 'SR', 'SJ', 'SZ', 'SE', 'CH', 'SY', 'TW', 'TJ', 'TZ', 'TH', 'TL', 'TG', 'TK', 'TO', 'TT', 'TN', 'TR', 'TM', 'TC', 'TV', 'UG', 'UA', 'AE', 'GB', 'US', 'UM', 'UY', 'UZ', 'VU', 'VE', 'VN', 'VG', 'VI', 'WF', 'EH', 'YE', 'ZM', 'ZW'
]
COUNTRY_CODES.sort()

session = requests.Session()

class Region:
	def __init__(self, code, parent=None):
		self.code = re.sub(r'[^A-Z0-9-]', '', code)
		self._validate_code(self.code)

		self.parent = parent
		if self.parent is not None:
			self._validate_code(self.parent)

		self.name = None
		self._is_special_name = False

	def set_name(self, name):
		is_special_name = False
		if '*' in name:
			is_special_name = True

		# Remove asterisks, parentheses and alternative names
		name = self._clean_name(name)
		assert(len(name) > 0)

		# If this is the first appearing name, use it meantime
		if self.name is None or self._is_special_name and not is_special_name:
			self.name = name
			self._is_special_name = is_special_name
			return True

		return False

	def _validate_code(self, code):
		if len(self.code) >= 4:
			assert(self.code[2] == '-')
		else:
			assert(len(self.code) == 2)

	def _clean_name(self, name):
		return re.sub(r'\(.*?\)|\[.*?\]|\*', '', name).strip()

	def __repr__(self):
		return 'Region<code="%s", parent="%s", name="%s">' % (self.code, self.parent, self.name)

def table_to_dicts(table):
	column_names = [header.text_content() for header in table.findall("thead/tr/th")]
	for row in table.findall("tbody/tr"):
		row_data = [cell.text_content() for cell in row.findall("td")]
		yield dict(zip(column_names, row_data))

def html_for_country(country_code):
	params = {
		'v-browserDetails': '1',
		'theme': 'iso-red',
		'v-appId': 'obpui-105541713',
		'v-loc': 'https://www.iso.org/obp/ui/en/#iso:code:3166:%s' % country_code,
		'v-wn': 'obpui-105541713-0.7195732873730467'
	}

	reply = session.post("https://www.iso.org/obp/ui/", data=params).json()

	# JSON in JSON. Go figure
	uidl = json.loads(reply['uidl'])

	# Now find the update whose location is related-pub
	for state in uidl['state'].values():
		if not 'childLocations' in state:
			continue

		for location in state['childLocations'].values():
			if location == 'related-pub':
				html = state['templateContents']
				html = lxml.html.fragment_fromstring(html)
				return html

	raise Exception('Cannot find state update for country %s' % country_code)

def extract_field_value(html, field_text):
	return html.xpath(".//div[text()='%s']/../div[@class='core-view-field-value'][1]" % field_text)[0].text_content().strip()

def extract_country_subdivisions(html):
	regions = {}
	country_code = extract_field_value(html, 'Alpha-2 code')
	country_name = extract_field_value(html, 'Short name lower case')
	country_region = Region(country_code)
	country_region.set_name(country_name)
	regions[country_code] = country_region

	subdivision_table = html.get_element_by_id("subdivision")

	for entry in table_to_dicts(subdivision_table):
		code = entry['3166-2 code'].strip()

		subdivision = regions.get(code)
		if subdivision is None:
			parent = entry['Parent subdivision'].strip()
			if parent == '':
				parent = country_code
			subdivision = Region(code, parent)
			regions[code] = subdivision

		subdivision.set_name(entry['Subdivision name'])

	return regions
	
def get_country_subdivisions(country_code):
	return extract_country_subdivisions(html_for_country(country_code))

def main(args):
	countries = COUNTRY_CODES
	if len(args) > 1:
		countries = args[1:]

	writer = csv.writer(sys.stdout, dialect='excel')
	writer.writerow(['code', 'name', 'parent'])
	for country in countries:
		for subdivision in get_country_subdivisions(country).values():
			writer.writerow([subdivision.code, subdivision.name, subdivision.parent or ''])
			sys.stdout.flush()

if __name__ == '__main__':
	sys.exit(main(sys.argv))
