import gzip
import os
import sys
import traceback
import xml.etree.cElementTree as etree
from multiprocessing import Pool


def get_all_ids(xml_file):
    try:
        if not os.path.exists(f"{xml_file}.txt"):
            print(f"Processing {xml_file}")
        else:
            print(f"Not processing {xml_file}, already done")
            return True

        ids = []
        with gzip.open(xml_file, "rb") as f:
            # get an iterable
            context = etree.iterparse(f, events=("start", "end"))
            # turn it into an iterator
            context = iter(context)
            # get the root element
            event, root = next(context)
            for event, elem in context:
                if event == "end":
                    if elem.tag == "MedlineCitation" or elem.tag == "BookDocument":
                        pmid_elem = elem.find("PMID")
                        ids.append(f"{int(pmid_elem.text)}:{pmid_elem.attrib['Version']}")

            with open(f"{xml_file}.txt", "w") as f:
                for fid in ids:
                    f.write(f"{fid}\n")
    except Exception as e:
        print(e)
        traceback.print_exc()
        raise
    return True


medline_path = "data/xmls/" if not len(sys.argv) > 1 else sys.argv[1]

paths = []
for root, dirs, files in os.walk(medline_path):
    for filename in files:
        if os.path.splitext(filename)[-1] in [".xml", ".gz"]:
            paths.append(os.path.join(root, filename))
paths.sort()


with Pool(processes=7) as pool:
    result = pool.map_async(get_all_ids, paths)
    result.get()
