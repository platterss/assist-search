# assist-search

Python data scraper for [ASSIST.org](https://www.assist.org). It is designed to minimize requests to ASSIST and store
data in a format that allows it to be easily "reverse searched."

This is also a [website]().

All the data collected is stored in the `data` folder (>400 MB) and is free to use. See the 
[wiki](https://github.com/platterss/assist-search/wiki) for information on how to use the data.

## Prerequisites

- Python 3.12
- [requests](https://pypi.org/project/requests/) (`pip install requests`)

## Usage

With a populated `data` folder, you can run `main.py` to search for articulations through the terminal:

```
python main.py
```

Articulation data can be fetched by running the articulations.py script.

```
python articulations.py <university types>
```

where university types are any of:
- CSU
- UC
- AICCU

For example, if you wanted to only get data for CSUs and UCs,
you would run:

```
python articulations.py CSU UC
```

The data will be populated in the `data` folder.

Keep in mind that **fetching articulation data will take a long time**. There are 115 CCCs and 23 CSUs, 9 UCs, and 31 
AICCUs (so 63 universities total). If there were agreements between all the CCCs and universities, it would take a 
**minimum** of 115 CCCs * 63 universities * 4 seconds per request = 28,980 seconds = **8.05 hours** to fetch all the 
data.

**It is unlikely you will need to fetch the articulation data yourself**. I have a script running to automatically
fetch and update the articulation data at least once a week. You can check the commit history to see when the data
was last updated (as well as all the articulation changes which is pretty cool).

## Contributions

Contributions are welcome! Feel free to create an [issue](https://github.com/platterss/assist-search/issues) if you
run into any problems, have any suggestions, or notice that the articulation data is super old. Submitting a 
[pull request](https://github.com/platterss/assist-search/pulls) is cool too.

I wrote all the code in a weekend so it probably isn't that great
