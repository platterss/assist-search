# assist-search

Python data scraper for [ASSIST.org](https://www.assist.org). It is designed to minimize requests to ASSIST and store
data in a format that allows it to be easily "reverse searched."

This is also a [website](https://platterss.github.io/assist-search/).

All the data collected is stored in the `data` folder (>600 MB) and is free to use. See the 
[wiki](https://github.com/platterss/assist-search/wiki) for information on how the data is formatted.

## Prerequisites

- Python 3.12
- [requests](https://pypi.org/project/requests/) (`pip install requests`)
- [orjson](https://pypi.org/project/orjson/) (`pip install orjson`)

## Usage

With a populated `data` folder, you can load up `index.html` in your web browser to search for articulations.

Articulation data can be scraped by running the `articulations.py` script.
It supports several flags to filter exactly what you want to scrape.

```bash
python articulations.py --types CSU UC AICCU
```

If no `--types` are provided, it defaults to all three. You can also target specific colleges
or universities by name or ID, or resume a stopped scrape using offsets:

```bash
# Only get data for a specific university
python articulations.py --universities "San Jose State University"

# Start scraping from a specific university onward
python articulations.py --after-university "University of California, Berkeley"
```

### Time Warning

Keep in mind that **fetching articulation data will take a long time**. There are 115 CCCs and 23 CSUs, 9 UCs, and 31 
AICCUs (so 63 universities total). This scraper makes, on average, 2.5 requests for each CCC → university with a 
cooldown of 3 seconds per request. It would take around 115 CCCs * 2.5 requests * 3 seconds/request * 63 universities = 
54,337.5 seconds = **15.09 hours** to fetch all the data. That's a pretty long time.

**You probably won't need to fetch the articulation data yourself**. I have a script running to automatically
fetch and update the articulation data at least once a week. You can check the commit history to see when the data
was last updated.

The space-saving format the JSON files are stored in makes them pretty inconvenient to look at the diff for,
but you can probably just use a text difference tool somewhere and cross-reference with the CC registry.

## Releases

In [Releases](https://github.com/platterss/assist-search/releases), there are two .zip files:
`data.zip` and `raw_agreements.zip`.

`data.zip` is just a compressed version of the `data` folder in the repo.

`raw_agreements.zip` contains the raw ASSIST.org articulation agreements collected in the latest automated run, 
particularly the categories and the
AllMajors/AllDepartments/AllGeneralEducation agreements.

Each folder is named by the university ID and each of the files within it use the format
`<sending institution ID>_<year ID>_<agreement type>.json`. For example, the AllMajors agreement between De Anza 
(ID 113) and UC Berkeley (ID 79) for the 25-26 academic year (ID 76) would be located in the folder `79` with the name 
`113_76_AllMajors.json`.

To use the raw agreements with this program:

1. Unzip `raw_agreements.zip` into the project root. There'll just be a `raw_agreements` folder there.
2. Add `--local` to the command line arguments.
3. Run `articulations.py`.

It'll take a few minutes to process all the data. Way better than 15 hours.

## Contributions

Contributions are welcome! Feel free to create an [issue](https://github.com/platterss/assist-search/issues) if you
run into any problems, have any suggestions, or notice that the articulation data is super old. Submitting a 
[pull request](https://github.com/platterss/assist-search/pulls) is cool too.

I wrote all the code in a weekend so it probably isn't that great
