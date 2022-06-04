import gzip
import os
import traceback
import xml.etree.cElementTree as etree
from multiprocessing import Pool

__version__ = "0.1.0"


def get_all_ids(xml_file):
    try:
        if not os.path.exists(f"{xml_file}.txt"):
            print(f"Processing {xml_file}")
        else:
            print(f"Not processing {xml_file}, already done")
            return True

        ids = []
        with gzip.open(xml_file, "rb") as f:
            context = etree.iterparse(f, events=("start", "end"))
            context = iter(context)
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


def ensure_id_files(paths, processes):
    with Pool(processes=processes) as pool:
        result = pool.map_async(get_all_ids, paths)
        result.get()
