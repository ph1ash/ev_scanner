import csv
import os
import re
from urllib.parse import urlparse

import requests
import structlog
from bs4 import BeautifulSoup

import constants

logger = structlog.get_logger()

CSV_FILE_NAME = "data.csv"


def _fetch_vehicle_data_from_db(url) -> BeautifulSoup:
    parsed_url = urlparse(url)
    vehicle_url = parsed_url.path.split("/")[-1]
    vehicle_id = parsed_url.path.split("/")[-2]
    file_path = f"pages/ev_database_{vehicle_id}_{vehicle_url}.html"

    if os.path.exists(file_path):
        logger.info(f"Reading from file: {file_path}")
        with open(file_path, "r") as file:
            content = file.read()
            soup = BeautifulSoup(content, "html.parser")
    else:
        logger.info(f"Fetching from internet and saving to file: {file_path}")
        response = requests.get(url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, "html.parser")
            with open(file_path, "w") as file:
                file.write(soup.prettify())
        else:
            # Print an error message if the request was not successful
            logger.error("Failed to retrieve data from the website.")
            return None

    return soup


def scrape_ev_database(vehicle_name: str, url: str):
    soup = _fetch_vehicle_data_from_db(url)
    # Find the elements containing the desired information
    data = [vehicle_name]
    try:
        for label in constants.FIELD_LABEL_LIST:
            element = soup.find("td", string=re.compile(label.label))
            data_value: str = element.next_element.next_element.next_element.text.strip()
            if label.label == "Charge Time":
                hours = int(data_value.split("h")[0])
                if "hours" not in data_value:
                    minutes = int(data_value.split("h")[1].split("m")[0])
                else:
                    minutes = 0
                data.append(hours * 60 + minutes)
            elif label.label == "Warranty Period":
                if "No Data" in data_value:
                    warranty_period = 0
                else:
                    warranty_period = int(data_value.split(" ")[0])
                data.append(warranty_period)
            elif label.label in constants.NON_SPLITTABLE_FIELDS:
                data.append(data_value)
            else:
                data_value = data_value.split(" ")[0]
                data.append(data_value)
    except AttributeError:
        logger.error(f"Failed to find the element: {label}")
        exit(1)
    return data


def main():
    # Write the header to the CSV file
    with open(CSV_FILE_NAME, "w", newline="") as file:
        writer = csv.writer(file)
        header = [
            "Vehicle Name",
            *map(
                lambda x: f"{x.label} ({x.unit})" if x.unit else x.label,
                constants.FIELD_LABEL_LIST,
            ),
        ]
        writer.writerow(header)

    for vehicle_url in constants.VEHICLES_TO_SCRAPE:
        vehicle_name = urlparse(vehicle_url).path.split("/")[-1]
        data = scrape_ev_database(vehicle_name, vehicle_url)
        with open(CSV_FILE_NAME, "a", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(data)


# Scrape the data from the webpage
if __name__ == "__main__":
    main()
