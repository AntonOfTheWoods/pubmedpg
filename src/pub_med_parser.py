import asyncio
import datetime
import gzip
import os
import time
import traceback
import warnings
import xml.etree.cElementTree as etree
from multiprocessing import Pool

from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pubmedpg.core.config import settings
from pubmedpg.db.base import Base
from pubmedpg.models.pubmed import (
    Abstract,
    Accession,
    Author,
    Chemical,
    Citation,
    CitationSubset,
    Comment,
    DataBank,
    GeneSymbol,
    Grant,
    Investigator,
    Journal,
    JournalInfo,
    Keyword,
    Language,
    MeshHeading,
    Note,
    OtherAbstract,
    OtherId,
    PersonalName,
    PublicationType,
    Qualifier,
    SpaceFlight,
    SupplMeshName,
    XmlFile,
)

sync_engine = create_engine(settings.SQLALCHEMY_DATABASE_URI)
# a sessionmaker(), also in the same scope as the engine
sync_session = Session(sync_engine)


WARNING_LEVEL = "always"  # error, ignore, always, default, module, once
# multiple processes, #processors-1 is optimal!
warnings.simplefilter(WARNING_LEVEL)

# convert 3 letter code of months to digits for unique publication format
MONTH_CODE = {
    "Jan": "01",
    "Feb": "02",
    "Mar": "03",
    "Apr": "04",
    "May": "05",
    "Jun": "06",
    "Jul": "07",
    "Aug": "08",
    "Sep": "09",
    "Oct": "10",
    "Nov": "11",
    "Dec": "12",
}


def es(xml_node, length, default=None):
    if xml_node is None or xml_node.text is None:
        return default
    else:
        stripped = xml_node.text.strip()
        return stripped[: length - 3] + "..." if len(stripped) > length else stripped


def init_person(person_node, person):
    person.last_name = es(person_node.find("LastName"), 300)
    person.fore_name = es(person_node.find("ForeName"), 100)
    person.initials = es(person_node.find("Initials"), 10)
    person.suffix = es(person_node.find("Suffix"), 20)
    return person


def get_date(elem):
    # Kersten: some dates are given in 3-letter code - use dictionary MONTH_CODE for conversion to digits:
    try:
        date = datetime.date(int(elem.find("Year").text), int(elem.find("Month").text), int(elem.find("Day").text))
    except Exception:
        date = datetime.date(
            int(elem.find("Year").text),
            int(MONTH_CODE[elem.find("Month").text]),
            int(elem.find("Day").text),
        )
    return date


def set_abstracts(db_citation: Citation, elem):
    if elem.tag != "Abstract":
        return
    abstracts = []
    db_abstract = Abstract()
    # prepare empty string for "normal" abstracts or "labelled" abstracts
    temp_abstract_text = ""
    # if there are multiple AbstractText-Tags:
    if elem.find("AbstractText") is not None and len(elem.findall("AbstractText")) > 1:
        for child_AbstractText in list(elem):
            # iteration over all labels is needed otherwise only "OBJECTIVE" would be pushed into database
            # debug: check label
            # [('NlmCategory', 'METHODS'), ('Label', 'CASE SUMMARY')]
            # ...
            # also checked for empty child-tags in this structure!
            if child_AbstractText.tag == "AbstractText" and child_AbstractText.text is not None:
                # if child_AbstractText.tag == "AbstractText": # would give an error!
                # no label - this case should not happen with multiple AbstractText-Tags:
                if len(list(child_AbstractText.items())) == 0:
                    temp_abstract_text += child_AbstractText.text + "\n"
                # one label or the NlmCategory - first index has to be zero:
                if len(list(child_AbstractText.items())) == 1:
                    # filter for the wrong label "UNLABELLED" - usually contains the text "ABSTRACT: - not used:
                    if list(child_AbstractText.items())[0][1] == "UNLABELLED":
                        temp_abstract_text += child_AbstractText.text + "\n"
                    else:
                        temp_abstract_text += (
                            list(child_AbstractText.items())[0][1] + ":\n" + child_AbstractText.text + "\n"
                        )
                # label and NlmCategory - take label - first index has to be one:
                if len(list(child_AbstractText.items())) == 2:
                    temp_abstract_text += (
                        list(child_AbstractText.items())[1][1] + ":\n" + child_AbstractText.text + "\n"
                    )
    # if there is only one AbstractText-Tag ("usually") - no labels used:
    if elem.find("AbstractText") is not None and len(elem.findall("AbstractText")) == 1:
        temp_abstract_text = elem.findtext("AbstractText")
    # append abstract text for later pushing it into db:
    db_abstract.abstract_text = temp_abstract_text
    # next 3 lines are unchanged - some abstract texts (few) contain the child-tag "CopyrightInformation" after all AbstractText-Tags:
    if elem.find("CopyrightInformation") is not None:
        db_abstract.copyright_information = elem.find("CopyrightInformation").text
    abstracts.append(db_abstract)
    db_citation.abstracts = abstracts


def set_keywords(db_citation, elem):
    if elem.tag != "KeywordList":
        return
    # catch KeyError in case there is no Owner attribute before committing db_citation
    try:
        db_citation.keyword_list_owner = elem.attrib["Owner"]
    except Exception:
        pass

    keywords = []
    all_keywords = []
    for subelem in elem:
        # some documents contain duplicate keywords which would lead to a key error - if-clause
        if subelem.text not in all_keywords:
            all_keywords.append(subelem.text[:1000] if subelem.text is not None else None)
        else:
            continue
        db_keyword = Keyword()
        if subelem.text is not None:
            db_keyword.keyword = subelem.text[:1000]
        # catch KeyError in case there is no MajorTopicYN attribute before committing db_citation
        try:
            db_keyword.keyword_major_yn = subelem.attrib["MajorTopicYN"]
        except Exception:
            pass

        # null check for keyword
        if db_keyword.keyword is not None:
            keywords.append(db_keyword)
    db_citation.keywords = keywords


def set_suppl_mesh_list(db_citation, elem):
    if elem.tag != "SupplMeshList":
        return
    db_citation.suppl_mesh_names = []
    for suppl_mesh in elem:
        db_suppl_mesh_name = SupplMeshName()
        db_suppl_mesh_name.suppl_mesh_name = es(suppl_mesh, 80)
        db_suppl_mesh_name.suppl_mesh_name_ui = suppl_mesh.attrib["UI"]
        db_suppl_mesh_name.suppl_mesh_name_type = suppl_mesh.attrib["Type"]
        db_citation.suppl_mesh_names.append(db_suppl_mesh_name)


def set_journal_issn(db_journal, elem):
    if elem.tag != "ISSN":
        return
    db_journal.issn = elem.text
    db_journal.issn_type = elem.attrib["IssnType"]


def set_journal_main_info(db_journal, elem, pubmed_id, db_xml_file):
    if elem.tag not in ["JournalIssue", "Book"]:
        return

    if elem.find("Volume") is not None:
        db_journal.volume = elem.find("Volume").text
    if elem.find("Issue") is not None:
        db_journal.issue = elem.find("Issue").text

    # ensure pub_date_year with boolean year:
    year = False
    for subelem in elem.find("PubDate"):
        if subelem.tag == "MedlineDate":
            db_journal.medline_date = es(subelem, 40)
        elif subelem.tag == "Year":
            year = True
            db_journal.pub_date_year = int(subelem.text) if subelem.text else None
        elif subelem.tag == "Month":
            if subelem.text in MONTH_CODE:
                db_journal.pub_date_month = MONTH_CODE[subelem.text]
            else:
                db_journal.pub_date_month = subelem.text
        elif subelem.tag == "Day":
            db_journal.pub_date_day = subelem.text
    # try to cast year from beginning of MedlineDate string
    if not year:
        try:
            db_journal.pub_date_year = int(subelem.text[0:4])
        except Exception:
            try:
                db_journal.pub_date_year = int(subelem.text[-4:])
            except Exception:
                print(f"Unable to get year for {pubmed_id=}: {db_xml_file.xml_file_name=}, {subelem.text=}")
                pass


def set_journal_article_date(db_journal, elem):
    # if there is the attribute ArticleDate, month and day are given
    if elem.tag != "ArticleDate":
        return
    db_journal.pub_date_year = elem.find("Year").text
    db_journal.pub_date_month = elem.find("Month").text
    db_journal.pub_date_day = elem.find("Day").text


def set_journal_title(db_journal, elem):
    if elem.tag != "Title":
        return
    """ToDo"""
    pass


def set_journal_title_iso(db_journal, elem):
    if elem.tag != "Journal":
        return
    if elem.find("Title") is not None:
        db_journal.title = elem.find("Title").text
    if elem.find("ISOAbbreviation") is not None:
        db_journal.iso_abbreviation = elem.find("ISOAbbreviation").text


def set_article_title(db_citation, elem):
    if elem.tag not in ["ArticleTitle", "BookTitle"]:
        return
    if elem.text is not None:
        db_citation.article_title = elem.text
    # add string because of not null constraint
    else:
        db_citation.article_title = "No title"


def set_authors(db_citation, elem):
    if elem.tag != "AuthorList":
        return
    # catch KeyError in case there is no CompleteYN attribute before committing db_citation
    try:
        db_citation.article_author_list_comp_yn = elem.attrib["CompleteYN"]
    except Exception:
        pass

    db_citation.authors = []
    for author in elem:
        db_author = init_person(author, Author())
        db_author.collective_name = es(author.find("CollectiveName"), 2700)
        db_citation.authors.append(db_author)


def set_personal_names(db_citation, elem):
    if elem.tag != "PersonalNameSubjectList":
        return
    db_citation.personal_names = []
    for pname in elem:
        db_citation.personal_names.append(init_person(pname, PersonalName()))


def set_investigators(db_citation, elem):
    if elem.tag != "InvestigatorList":
        return
    db_citation.investigators = []
    for investigator in elem:
        db_investigator = init_person(investigator, Investigator())
        if investigator.find("Affiliation") is not None:
            db_investigator.investigator_affiliation = investigator.find("Affiliation").text
        db_citation.investigators.append(db_investigator)


def set_space_flight(db_citation, elem):
    if elem.tag != "SpaceFlightMission":
        return
    db_space_flight = SpaceFlight()
    db_space_flight.space_flight_mission = elem.text
    db_citation.space_flights = [db_space_flight]


def set_notes(db_citation, elem):
    if elem.tag != "GeneralNote":
        return
    db_citation.notes = []
    for subelem in elem:
        db_note = Note()
        db_note.general_note_owner = elem.attrib["Owner"]
        db_note.general_note = subelem.text
        db_citation.notes.append(db_note)


def set_chemicals(db_citation, elem):
    if elem.tag != "ChemicalList":
        return
    db_citation.chemicals = []
    for chemical in elem:
        db_chemical = Chemical()
        if chemical.find("RegistryNumber") is not None:
            db_chemical.registry_number = chemical.find("RegistryNumber").text
        if chemical.find("NameOfSubstance") is not None:
            db_chemical.name_of_substance = chemical.find("NameOfSubstance").text
            db_chemical.substance_ui = chemical.find("NameOfSubstance").attrib["UI"]
        db_citation.chemicals.append(db_chemical)


def set_gene_symbols(db_citation, elem):
    if elem.tag != "GeneSymbolList":
        return
    db_citation.gene_symbols = []
    for genes in elem:
        db_gene_symbol = GeneSymbol()
        db_gene_symbol.gene_symbol = genes.text[:37] + "..." if len(genes.text) > 40 else genes.text
        db_citation.gene_symbols.append(db_gene_symbol)


def set_comment_corrections(db_citation, elem):
    if elem.tag != "CommentsCorrectionsList":
        return
    db_citation.comments = []
    for comment in elem:
        db_comment = Comment()
        db_comment.ref_source = es(comment.find("RefSource"), 255, "No reference source")
        if comment.attrib["RefType"] is not None:
            if len(comment.attrib["RefType"]) > 21:
                db_comment.ref_type = comment.attrib["RefType"][:18] + "..."
            else:
                db_comment.ref_type = comment.attrib["RefType"]

        comment_pmid_version = comment.find("PMID")
        if comment_pmid_version is not None:
            db_comment.pmid_version = int(comment_pmid_version.text)
        db_citation.comments.append(db_comment)


def set_journal_infos(db_citation, elem):
    if elem.tag != "MedlineJournalInfo":
        return
    db_journal_info = JournalInfo()
    if elem.find("NlmUniqueID") is not None:
        db_journal_info.nlm_unique_id = elem.find("NlmUniqueID").text
    if elem.find("Country") is not None:
        db_journal_info.country = elem.find("Country").text
    """#MedlineTA is just a name for the journal as an abbreviation
    Abstract with PubMed-ID 21625393 has no MedlineTA attributebut it has to be set in PostgreSQL, that is why "unknown" is inserted instead. There is just a <MedlineTA/> tag and the same information is given in  </JournalIssue> <Title>Biotechnology and bioprocess engineering : BBE</Title>, but this is not (yet) read in this parser -> line 173:
    """
    if elem.find("MedlineTA") is not None and elem.find("MedlineTA").text is None:
        db_journal_info.medline_ta = "unknown"
    elif elem.find("MedlineTA") is not None:
        db_journal_info.medline_ta = elem.find("MedlineTA").text
    db_citation.journal_infos = [db_journal_info]


def set_citation_subsets(db_citation, elem):
    if elem.tag != "CitationSubset":
        return
    db_citation.citation_subsets = []
    for subelem in elem:
        db_citation_subset = CitationSubset(subelem.text)
        db_citation.citation_subsets.append(db_citation_subset)


def set_mesh_headings(db_citation, elem):
    if elem.tag != "MeshHeadingList":
        return
    db_citation.meshheadings = []
    db_citation.qualifiers = []
    for mesh in elem:
        db_mesh_heading = MeshHeading()
        mesh_desc = mesh.find("DescriptorName")
        if mesh_desc is not None:
            db_mesh_heading.descriptor_name = mesh_desc.text
            db_mesh_heading.descriptor_name_major_yn = mesh_desc.attrib["MajorTopicYN"]
            db_mesh_heading.descriptor_ui = mesh_desc.attrib["UI"]
        if mesh.find("QualifierName") is not None:
            mesh_quals = mesh.findall("QualifierName")
            for qual in mesh_quals:
                db_qualifier = Qualifier()
                db_qualifier.descriptor_name = mesh_desc.text
                db_qualifier.qualifier_name = qual.text
                db_qualifier.qualifier_name_major_yn = qual.attrib["MajorTopicYN"]
                db_qualifier.qualifier_ui = qual.attrib["UI"]
                db_citation.qualifiers.append(db_qualifier)
        db_citation.meshheadings.append(db_mesh_heading)


def set_other_ids(db_citation: Citation, elem):
    if elem.tag != "OtherID":
        return
    other_ids = []
    db_other_id = OtherId()
    db_other_id.other_id = es(elem, 80)
    db_other_id.other_id_source = elem.attrib["Source"]
    other_ids.append(db_other_id)
    db_citation.other_ids = other_ids


def set_other_abstracts(db_citation: Citation, elem):
    if elem.tag != "OtherAbstract":
        return

    other_abstracts = []
    db_other_abstract = OtherAbstract()
    for other in elem:
        if other.tag == "AbstractText":
            db_other_abstract.other_abstract = other.text
    other_abstracts.append(db_other_abstract)
    db_citation.other_abstracts = other_abstracts


def set_publication_types(db_citation, elem):
    if elem.tag != "PublicationTypeList":
        return
    publication_types = []
    all_publication_types = []
    for subelem in elem:
        # check for unique elements in PublicationTypeList
        if subelem.text not in all_publication_types:
            db_publication_type = PublicationType()
            db_publication_type.publication_type = subelem.text
            publication_types.append(db_publication_type)
            all_publication_types.append(subelem.text)
    db_citation.publication_types = publication_types


def set_languages(db_citation, elem):
    if elem.tag != "Language":
        return
    db_language = Language()
    db_language.language = elem.text
    db_citation.languages = [db_language]


def set_databanks_accessions(db_citation, elem):
    if elem.tag != "DataBankList":
        return

    # catch KeyError in case there is no CompleteYN attribute before committing db_citation
    try:
        db_citation.data_bank_list_complete_yn = elem.attrib["CompleteYN"]
    except Exception:
        pass
    db_citation.accessions = []
    db_citation.databanks = []

    all_databanks = []
    all_acc_numbers = {}

    for databank in elem:
        temp_name = databank.find("DataBankName").text
        # check unique data_bank_name per PubMed ID and not null
        if temp_name is not None and temp_name not in all_databanks:
            db_data_bank = DataBank()
            db_data_bank.data_bank_name = temp_name
            db_citation.databanks.append(db_data_bank)
            all_databanks.append(temp_name)
            all_acc_numbers[temp_name] = []

        acc_numbers = databank.find("AccessionNumberList")

        if acc_numbers is not None and temp_name is not None:
            for acc_number in acc_numbers:
                # check unique accession number per PubMed ID and data_bank_name
                if acc_number.text and acc_number.text not in all_acc_numbers[temp_name]:
                    db_accession = Accession()
                    db_accession.data_bank_name = db_data_bank.data_bank_name
                    db_accession.accession_number = es(acc_number, 200)
                    db_citation.accessions.append(db_accession)
                    all_acc_numbers[temp_name].append(es(acc_number, 200))


def set_grants(db_citation, elem):
    if elem.tag != "GrantList":
        return
    # catch KeyError in case there is no CompleteYN attribute before committing db_citation
    try:
        db_citation.grant_list_complete_yn = elem.attrib["CompleteYN"]
    except Exception:
        pass
    db_citation.grants = []
    for grant in elem:
        db_grants = Grant()
        db_grants.grantid = es(grant.find("GrantID"), 200)
        db_grants.acronym = es(grant.find("Acronym"), 20)
        db_grants.agency = es(grant.find("Agency"), 200)
        db_grants.country = es(grant.find("Country"), 200)
        db_citation.grants.append(db_grants)


def set_article(db_citation, elem):
    if elem.tag != "Article":
        return
    # ToDo
    """
    for subelem in elem:
        if subelem.tag == "Journal":
            for sub_subelem in subelem:
                pass
        if subelem.tag == "JArticleTitle":
            pass
        if subelem.tag == "JPagination":
            pass
        if subelem.tag == "JLanguage":
            pass
        if subelem.tag == "JPublicationTypeList":
            pass
    """


def set_owner_status(db_citation, elem):
    # catch KeyError in case there is no Owner or Status attribute before committing db_citation
    try:
        db_citation.citation_owner = elem.attrib["Owner"]
    except Exception:
        pass
    try:
        db_citation.citation_status = elem.attrib["Status"]
    except Exception:
        pass


def set_citation_journal_values(db_citation, db_journal, elem, pubmed_id, db_xml_file):
    if elem.tag == "DateCreated":
        db_citation.date_created = get_date(elem)
    if elem.tag == "DateCompleted":
        db_citation.date_completed = get_date(elem)
    if elem.tag == "DateRevised":
        db_citation.date_revised = get_date(elem)
    if elem.tag == "NumberOfReferences":
        db_citation.number_of_references = int(elem.text) if elem.text else 0

    set_journal_issn(db_journal, elem)
    set_journal_main_info(db_journal, elem, pubmed_id, db_xml_file)
    set_journal_article_date(db_journal, elem)
    set_journal_title(db_journal, elem)
    set_journal_title_iso(db_journal, elem)

    set_article_title(db_citation, elem)
    if elem.tag == "MedlinePgn":
        db_citation.medline_pgn = elem.text
    set_authors(db_citation, elem)
    set_personal_names(db_citation, elem)
    set_investigators(db_citation, elem)
    set_space_flight(db_citation, elem)
    set_notes(db_citation, elem)
    set_chemicals(db_citation, elem)
    set_gene_symbols(db_citation, elem)
    set_comment_corrections(db_citation, elem)
    set_journal_infos(db_citation, elem)
    set_citation_subsets(db_citation, elem)
    set_mesh_headings(db_citation, elem)
    set_grants(db_citation, elem)
    set_databanks_accessions(db_citation, elem)
    set_languages(db_citation, elem)
    set_publication_types(db_citation, elem)
    set_article(db_citation, elem)
    if elem.tag == "VernacularTitle":
        db_citation.vernacular_title = elem.tag
    set_other_abstracts(db_citation, elem)
    set_other_ids(db_citation, elem)
    set_abstracts(db_citation, elem)
    set_keywords(db_citation, elem)
    if elem.tag == "Affiliation":
        db_citation.article_affiliation = es(elem, 2000)
    set_suppl_mesh_list(db_citation, elem)


good_entries = {}


class MedlineParser:
    def __init__(self, filepath):
        self.filepath = filepath
        # self.good_entries = filepath[1]
        engine = create_engine(settings.SQLALCHEMY_DATABASE_URI)
        self.session = Session(engine)

    def __del__(self):
        if self.session:
            self.session.close()

    def already_parsed(self, xml_name):
        # logfile = os.path.join(os.path.dirname(self.filepath), "processed_xmls.txt")
        # if os.path.exists(logfile):
        #     with open(logfile, "r") as f:
        #         processed_xmls = set(f.read().splitlines())
        # else:
        #     processed_xmls = set()
        # if self.filepath in processed_xmls:
        #     print(f"Processing file: {self.filepath} already processed")
        #     return True
        a = self.session.query(XmlFile.xml_file_name).filter_by(xml_file_name=xml_name)
        if a.all():
            print(f"Processing file: {self.filepath}, {datetime.datetime.now()} already processed")
            return True
        return False

    def manage_updates(self):
        ...
        # The following condition is only for incremental updates.
        """
        # Implementation that replaces the database entry with the new article from the XML file.
        if same_pmid: # -> evt. any()
            same_pmid = same_pmid[0]
            warnings.warn('\nDoubled Citation found (%s).' % pubmed_id)
            if not same_pmid.date_revised or same_pmid.date_revised < db_citation.date_revised:
                warnings.warn('\nReplace old Citation. Old Citation from %s, new citation from %s.' % (same_pmid.date_revised, db_citation.date_revised) )
                self.session.delete( same_pmid )
                self.session.commit()
                db_citation.xml_files = [db_xml_file] # adds an implicit add()
                self.session.add( db_citation )
        """

        # Keep database entry that is already saved in database and continue with the next PubMed-ID.
        # Manually deleting entries is possible (with PGAdmin3 or via command-line), e.g.:
        # DELETE FROM pubmed.tbl_medline_citation WHERE pmid = 25005691;
        # if same_pmid:
        #     print(
        #         "Article already in database - " + str(same_pmid[0]) + "Continuing with next PubMed-ID"
        #     )
        #     db_citation = Citation()
        #     db_journal = Journal()
        #     elem.clear()
        #     await self.session.commit()
        #     continue
        # else:

    def parse(self):
        try:
            xml_name = os.path.split(self.filepath)[-1]
            if self.already_parsed(xml_name):
                return True
            # existing_ids = set()
            # existing_ids_file = f"{self.filepath}.txt"
            # if os.path.exists(existing_ids_file):
            #     tmp_existing = []
            #     with open(existing_ids_file, "r") as f:
            #         for line in f:
            #             if line.strip():
            #                 tmp_existing.append(line.split(":")[0].strip())
            #     result = self.session.execute(select(Citation.pmid).where(Citation.pmid.in_(tmp_existing)))
            #     existing_ids = set(result.scalars().all())

            _file = self.filepath
            if os.path.splitext(self.filepath)[-1] == ".gz":
                _file = gzip.open(_file, "rb")

            # get an iterable
            context = etree.iterparse(_file, events=("start", "end"))
            # turn it into an iterator
            context = iter(context)

            # get the root element
            event, root = next(context)

            db_citation = Citation()
            db_journal = Journal()

            db_xml_file = XmlFile()
            db_xml_file.xml_file_name = xml_name
            db_xml_file.time_processed = datetime.datetime.now()  # time.localtime()

            loop_counter = 0  # to check for memory usage each X loops
            already_present = 0
            pubmed_id = 0
            file_ids_processed = set()
            # print(f"{len(good_entries)=}")
            for event, elem in context:
                if event == "end":
                    if elem.tag == "MedlineCitation" or elem.tag == "BookDocument":
                        loop_counter += 1
                        # if loop_counter % 2000 == 0:
                        #     print(f"{xml_name=}: {loop_counter=}")
                        set_owner_status(db_citation, elem)
                        db_citation.journals = [db_journal]

                        pubmed_id = int(elem.find("PMID").text)
                        db_citation.pmid = pubmed_id

                        try:
                            # same_pmid = False
                            # result = self.session.execute(select(Citation).where(Citation.pmid == pubmed_id))
                            # same_pmid = len(result.scalars().all()) > 0
                            if pubmed_id in file_ids_processed or good_entries.get(pubmed_id) != xml_name:
                                # print(f"{pubmed_id=}, {good_entries.get(pubmed_id)=}, {xml_name=}")
                                already_present += 1
                                db_citation = Citation()
                                db_journal = Journal()
                                elem.clear()
                                continue
                            file_ids_processed.add(pubmed_id)
                            # self.manage_updates()
                            db_citation.xml_files = [db_xml_file]  # adds an implicit add()
                            self.session.add(db_citation)

                        except IntegrityError as error:
                            warnings.warn(f"\nFile: {db_xml_file.xml_file_name}\nIntegrityError: {error}", Warning)
                            self.session.rollback()
                            raise
                        except Exception as e:
                            warnings.warn(f"\nFile: {db_xml_file.xml_file_name}\nUnknown error: {e}", Warning)
                            self.session.rollback()
                            raise

                        db_citation = Citation()
                        db_journal = Journal()
                        elem.clear()
                    set_citation_journal_values(db_citation, db_journal, elem, pubmed_id, db_xml_file)

            self.session.commit()
            print(
                f"Finishing file: {self.filepath}, {datetime.datetime.now()} with {loop_counter=} citations"
                f" {already_present=}."
            )
            return True
        except Exception as e:
            warnings.warn(f"\nFile: {self.filepath}\nUnknown error: {e}", Warning)
            traceback.print_exc()
            self.session.rollback()
            return False


def get_memory_usage(pid=os.getpid(), format="%mem"):
    """
    Get the Memory Usage from a specific process
    @pid = Process ID
    @format = % or kb (%mem or rss) ...
    """
    return float(os.popen("ps -p %d -o %s | tail -1" % (pid, format)).read().strip())


def _start_parser(path):
    """
    Used to start MultiProcessor Parsing
    """
    print(f"Processing file: {path=}, {datetime.datetime.now()}, pid: {os.getpid()=}")
    # asyncio.run(MedlineParser(path_and_check[0])._parse(path_and_check[1]))
    MedlineParser(path).parse()
    return True


async def gather_with_concurrency(n, *tasks):
    semaphore = asyncio.Semaphore(n)

    async def sem_task(task):
        async with semaphore:
            return await task

    return await asyncio.gather(*(sem_task(task) for task in tasks))


def refresh_tables():
    try:
        Base.metadata.drop_all(sync_engine)
        Base.metadata.create_all(sync_engine)
    except Exception:
        print("Can't refresh tables")
        raise


def run(medline_path, clean, start, end, processes, baseline):
    end = int(end) if end else None

    if clean:
        refresh_tables()
    xml_paths = []
    xml_ids_paths = []
    for root, dirs, files in os.walk(medline_path):
        for filename in files:
            # if os.path.splitext(filename)[-1] in [".xml", ".gz"]:
            if filename.endswith(".xml") or filename.endswith(".xml.gz"):
                xml_paths.append(os.path.join(root, filename))
            elif filename.endswith(".xml.txt") or filename.endswith(".xml.gz.txt"):
                xml_ids_paths.append(os.path.join(root, filename))
    xml_paths.sort()
    xml_ids_paths.sort()
    # print("the xml_ids_paths: ", xml_ids_paths)
    # print("the xml_paths: ", xml_paths)
    print(f"Found {len(xml_paths)} files to parse.")
    print(f"Found {len(xml_ids_paths)} id files to parse and load.")
    for xml_ids_path in xml_ids_paths:
        with open(xml_ids_path, "r") as f:
            for line in f:
                if line.strip():
                    good_entries[int(line.split(":")[0].strip())] = os.path.basename(xml_ids_path).removesuffix(".txt")

    # print("found some stuffs: ", len(good_entries), list(good_entries.items())[:10])
    # import sys; sys.exit(0)
    with Pool(processes=processes) as pool:
        result = pool.map_async(_start_parser, xml_paths[start:end])
        result.wait()
        result.get()

    # without multiprocessing:
    # for path in paths:
    #    _start_parser(( path, existing,))

    # with async
    # asyncio.run(gather_with_concurrency(10, *([MedlineParser(apath)._parse() for apath in paths[start:end]])))


if __name__ == "__main__":
    start = os.environ.get("PMPG_FILELIST_START", 0)
    end = os.environ.get("PMPG_FILELIST_END", None)
    processes = os.environ.get("PMPG_PROCESSES", 2)
    baseline = str(os.environ.get("PMPG_BASELINE", False)).lower() == "true"
    medline_path = os.environ.get("PMPG_MEDLINE_PATH", "data/xmls/")
    clean = str(os.environ.get("PMPG_CLEAN", False)).lower() == "true"

    print(f"Launching with {start=}, {end=}, {processes=}, {medline_path=}, {clean=}, {baseline=}")
    # log start time of programme:
    before = time.asctime()
    run(medline_path, clean, int(start), end, int(processes), baseline)
    # end time programme
    after = time.asctime()

    print("############################################################")
    print(f"Programme started: {before} - ended: {after}")
    print("############################################################")
