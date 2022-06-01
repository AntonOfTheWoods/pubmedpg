import asyncio
import datetime
import gzip
import os
import time
import warnings
import xml.etree.cElementTree as etree
from multiprocessing import Pool

from sqlalchemy import select

from pubmedpg.db.base import Base
from pubmedpg.db.session import get_session, sync_engine, sync_session
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

WARNING_LEVEL = "always"  # error, ignore, always, default, module, once
# multiple processes, #processors-1 is optimal!
PROCESSES = 4

warnings.simplefilter(WARNING_LEVEL)

# convert 3 letter code of months to digits for unique publication format
month_code = {
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


class MedlineParser:
    # db is a global variable and given to MedlineParser(path,db) in _start_parser(path)
    def __init__(self, filepath):
        self.filepath = filepath

    async def _parse(self, check_existing):
        _file = self.filepath

        """
        a = self.session.query(PubMedDB.XMLFile.xml_file_name).filter_by(xml_file_name = os.path.split(self.filepath)[-1])
        if a.all():
            print self.filepath, 'already in DB'
            return True
        """

        print("Parsing file:", _file)

        if os.path.splitext(_file)[-1] == ".gz":
            _file = gzip.open(_file, "rb")

        # get an iterable
        context = etree.iterparse(_file, events=("start", "end"))
        # turn it into an iterator
        context = iter(context)

        # get the root element
        event, root = next(context)

        DBCitation = Citation()
        DBJournal = Journal()

        DBXMLFile = XmlFile()
        DBXMLFile.xml_file_name = os.path.split(self.filepath)[-1]
        DBXMLFile.time_processed = datetime.datetime.now()  # time.localtime()

        loop_counter = 0  # to check for memory usage each X loops
        async with get_session() as db:
            for event, elem in context:
                if event == "end":
                    if elem.tag == "MedlineCitation" or elem.tag == "BookDocument":
                        loop_counter += 1
                        # catch KeyError in case there is no Owner or Status attribute before committing DBCitation
                        try:
                            DBCitation.citation_owner = elem.attrib["Owner"]
                        except Exception:
                            pass
                        try:
                            DBCitation.citation_status = elem.attrib["Status"]
                        except Exception:
                            pass
                        DBCitation.journals = [DBJournal]

                        pubmed_id = int(elem.find("PMID").text)
                        DBCitation.pmid = pubmed_id

                        # try:
                        same_pmid = None
                        if check_existing:
                            result = await db.execute(select(Citation).where(Citation.pmid == pubmed_id))
                            same_pmid = result.scalars().all()

                        # The following condition is only for incremental updates.
                        """
                        # Implementation that replaces the database entry with the new article from the XML file.
                        if same_pmid: # -> evt. any()
                            same_pmid = same_pmid[0]
                            warnings.warn('\nDoubled Citation found (%s).' % pubmed_id)
                            if not same_pmid.date_revised or same_pmid.date_revised < DBCitation.date_revised:
                                warnings.warn('\nReplace old Citation. Old Citation from %s, new citation from %s.' % (same_pmid.date_revised, DBCitation.date_revised) )
                                self.session.delete( same_pmid )
                                self.session.commit()
                                DBCitation.xml_files = [DBXMLFile] # adds an implicit add()
                                self.session.add( DBCitation )
                        """

                        # Keep database entry that is already saved in database and continue with the next PubMed-ID.
                        # Manually deleting entries is possible (with PGAdmin3 or via command-line), e.g.:
                        # DELETE FROM pubmed.tbl_medline_citation WHERE pmid = 25005691;
                        if same_pmid:
                            print(
                                "Article already in database - " + str(same_pmid[0]) + "Continuing with next PubMed-ID"
                            )
                            DBCitation = Citation()
                            DBJournal = Journal()
                            elem.clear()
                            await db.commit()
                            continue
                        else:
                            DBCitation.xml_files = [DBXMLFile]  # adds an implicit add()
                            db.add(DBCitation)

                        if loop_counter % 5000 == 0:
                            print("Committing on:", _file)
                            await db.commit()

                        # except IntegrityError as error:
                        #     warnings.warn("\nIntegrityError: " + str(error), Warning)
                        #     await db.rollback()
                        # except Exception as e:
                        #     warnings.warn("\nUnknown error:" + str(e), Warning)
                        #     await db.rollback()
                        #     raise

                        DBCitation = Citation()
                        DBJournal = Journal()
                        elem.clear()

                    # Kersten: some dates are given in 3-letter code - use dictionary month_code for conversion to digits:
                    if elem.tag == "DateCreated":
                        try:
                            date = datetime.date(
                                int(elem.find("Year").text), int(elem.find("Month").text), int(elem.find("Day").text)
                            )
                        except Exception:
                            date = datetime.date(
                                int(elem.find("Year").text),
                                int(month_code[elem.find("Month").text]),
                                int(elem.find("Day").text),
                            )
                        DBCitation.date_created = date

                    if elem.tag == "DateCompleted":
                        try:
                            date = datetime.date(
                                int(elem.find("Year").text), int(elem.find("Month").text), int(elem.find("Day").text)
                            )
                        except Exception:
                            date = datetime.date(
                                int(elem.find("Year").text),
                                int(month_code[elem.find("Month").text]),
                                int(elem.find("Day").text),
                            )
                        DBCitation.date_completed = date

                    if elem.tag == "DateRevised":
                        try:
                            date = datetime.date(
                                int(elem.find("Year").text), int(elem.find("Month").text), int(elem.find("Day").text)
                            )
                        except Exception:
                            date = datetime.date(
                                int(elem.find("Year").text),
                                int(month_code[elem.find("Month").text]),
                                int(elem.find("Day").text),
                            )
                        DBCitation.date_revised = date

                    if elem.tag == "NumberOfReferences":
                        DBCitation.number_of_references = int(elem.text) if elem.text else 0

                    if elem.tag == "ISSN":
                        DBJournal.issn = elem.text
                        DBJournal.issn_type = elem.attrib["IssnType"]

                    if elem.tag == "JournalIssue" or elem.tag == "Book":
                        if elem.find("Volume") is not None:
                            DBJournal.volume = elem.find("Volume").text
                        if elem.find("Issue") is not None:
                            DBJournal.issue = elem.find("Issue").text

                        # ensure pub_date_year with boolean year:
                        year = False
                        for subelem in elem.find("PubDate"):
                            if subelem.tag == "MedlineDate":
                                if len(subelem.text) > 40:
                                    DBJournal.medline_date = subelem.text[:37] + "..."
                                else:
                                    DBJournal.medline_date = subelem.text
                            elif subelem.tag == "Year":
                                year = True
                                DBJournal.pub_date_year = int(subelem.text) if subelem.text else None
                            elif subelem.tag == "Month":
                                if subelem.text in month_code:
                                    DBJournal.pub_date_month = month_code[subelem.text]
                                else:
                                    DBJournal.pub_date_month = subelem.text
                            elif subelem.tag == "Day":
                                DBJournal.pub_date_day = subelem.text
                        # try to cast year from beginning of MedlineDate string
                        if not year:
                            try:
                                temp_year = int(subelem.text[0:4])
                                DBJournal.pub_date_year = temp_year
                                year = True
                            except Exception:
                                print(_file, " not able to cast first 4 letters of medline_date", subelem.text)
                        # try to cast year from end of MedlineDate string
                        if not year:
                            try:
                                temp_year = int(subelem.text[-4:])
                                DBJournal.pub_date_year = temp_year
                                year = True
                            except Exception:
                                print(_file, " not able to cast last 4 letters of medline_date", subelem.text)

                    # if there is the attribute ArticleDate, month and day are given
                    if elem.tag == "ArticleDate":
                        DBJournal.pub_date_year = elem.find("Year").text
                        DBJournal.pub_date_month = elem.find("Month").text
                        DBJournal.pub_date_day = elem.find("Day").text

                    if elem.tag == "Title":
                        """ToDo"""
                        pass

                    if elem.tag == "Journal":
                        if elem.find("Title") is not None:
                            DBJournal.title = elem.find("Title").text
                        if elem.find("ISOAbbreviation") is not None:
                            DBJournal.iso_abbreviation = elem.find("ISOAbbreviation").text

                    if elem.tag == "ArticleTitle" or elem.tag == "BookTitle":
                        if elem.text is not None:
                            DBCitation.article_title = elem.text
                        # add string because of not null constraint
                        else:
                            DBCitation.article_title = "No title"
                    if elem.tag == "MedlinePgn":
                        DBCitation.medline_pgn = elem.text

                    if elem.tag == "AuthorList":
                        # catch KeyError in case there is no CompleteYN attribute before committing DBCitation
                        try:
                            DBCitation.article_author_list_comp_yn = elem.attrib["CompleteYN"]
                        except Exception:
                            pass

                        DBCitation.authors = []
                        for author in elem:
                            DBAuthor = Author()

                            if author.find("LastName") is not None:
                                DBAuthor.last_name = author.find("LastName").text

                            # Forname is restricted to 100 characters
                            if author.find("ForeName") is not None and author.find("ForeName").text is not None:
                                temp_forname = author.find("ForeName").text
                                if len(temp_forname) < 100:
                                    DBAuthor.fore_name = temp_forname
                                else:
                                    DBAuthor.fore_name = temp_forname[0:97] + "..."

                            if author.find("Initials") is not None:
                                temp_initials = author.find("Initials").text
                                if len(temp_initials) < 10:
                                    DBAuthor.initials = temp_initials
                                else:
                                    DBAuthor.initials = temp_initials[0:7] + "..."

                            # Suffix is restricted to 20 characters
                            if author.find("Suffix") is not None and author.find("Suffix").text is not None:
                                temp_suffix = author.find("Suffix").text
                                if len(temp_suffix) < 20:
                                    DBAuthor.suffix = temp_suffix
                                else:
                                    DBAuthor.suffix = temp_suffix[0:17] + "..."

                            if author.find("CollectiveName") is not None:
                                DBAuthor.collective_name = author.find("CollectiveName").text

                            DBCitation.authors.append(DBAuthor)

                    if elem.tag == "PersonalNameSubjectList":
                        DBCitation.personal_names = []
                        for pname in elem:
                            DBPersonalName = PersonalName()

                            if pname.find("LastName") is not None:
                                DBPersonalName.last_name = pname.find("LastName").text
                            if pname.find("ForeName") is not None:
                                DBPersonalName.fore_name = pname.find("ForeName").text
                            if pname.find("Initials") is not None:
                                DBPersonalName.initials = pname.find("Initials").text
                            if pname.find("Suffix") is not None:
                                DBPersonalName.suffix = pname.find("Suffix").text

                            DBCitation.personal_names.append(DBPersonalName)

                    if elem.tag == "InvestigatorList":
                        DBCitation.investigators = []
                        for investigator in elem:
                            DBInvestigator = Investigator()

                            if investigator.find("LastName") is not None:
                                DBInvestigator.last_name = investigator.find("LastName").text

                            if investigator.find("ForeName") is not None:
                                DBInvestigator.fore_name = investigator.find("ForeName").text

                            if investigator.find("Initials") is not None:
                                DBInvestigator.initials = investigator.find("Initials").text

                            if investigator.find("Suffix") is not None:
                                temp_suffix = investigator.find("Suffix").text
                                # suffix is restricted to 20 characters
                                if len(temp_suffix) < 20:
                                    DBInvestigator.suffix = temp_suffix
                                else:
                                    DBInvestigator.suffix = temp_suffix[:17] + "..."

                            if investigator.find("Affiliation") is not None:
                                DBInvestigator.investigator_affiliation = investigator.find("Affiliation").text

                            DBCitation.investigators.append(DBInvestigator)

                    if elem.tag == "SpaceFlightMission":
                        DBSpaceFlight = SpaceFlight()
                        DBSpaceFlight.space_flight_mission = elem.text
                        DBCitation.space_flights = [DBSpaceFlight]

                    if elem.tag == "GeneralNote":
                        DBCitation.notes = []
                        for subelem in elem:
                            DBNote = Note()
                            DBNote.general_note_owner = elem.attrib["Owner"]
                            DBNote.general_note = subelem.text
                            DBCitation.notes.append(DBNote)

                    if elem.tag == "ChemicalList":
                        DBCitation.chemicals = []
                        for chemical in elem:
                            DBChemical = Chemical()

                            if chemical.find("RegistryNumber") is not None:
                                DBChemical.registry_number = chemical.find("RegistryNumber").text
                            if chemical.find("NameOfSubstance") is not None:
                                DBChemical.name_of_substance = chemical.find("NameOfSubstance").text
                                DBChemical.substance_ui = chemical.find("NameOfSubstance").attrib["UI"]
                            DBCitation.chemicals.append(DBChemical)

                    if elem.tag == "GeneSymbolList":
                        DBCitation.gene_symbols = []
                        for genes in elem:
                            DBGeneSymbol = GeneSymbol()
                            if len(genes.text) < 40:
                                DBGeneSymbol.gene_symbol = genes.text
                            else:
                                DBGeneSymbol.gene_symbol = genes.text[:37] + "..."
                            DBCitation.gene_symbols.append(DBGeneSymbol)

                    if elem.tag == "CommentsCorrectionsList":

                        DBCitation.comments = []
                        for comment in elem:
                            DBComment = Comment()
                            comment_ref_type = comment.attrib["RefType"]
                            comment_ref_source = comment.find("RefSource")

                            if comment_ref_source is not None and comment_ref_source.text is not None:
                                if len(comment_ref_source.text) < 255:
                                    DBComment.ref_source = comment_ref_source.text
                                else:
                                    DBComment.ref_source = comment_ref_source.text[0:251] + "..."
                            # add string because of not null constraint
                            else:
                                DBComment.ref_source = "No reference source"

                            if comment_ref_type is not None:
                                if len(comment_ref_type) < 22:
                                    DBComment.ref_type = comment_ref_type
                                else:
                                    DBComment.ref_type = comment_ref_type[0:18] + "..."
                            comment_pmid_version = comment.find("PMID")

                            if comment_pmid_version is not None:
                                DBComment.pmid_version = int(comment_pmid_version.text)
                            DBCitation.comments.append(DBComment)

                    if elem.tag == "MedlineJournalInfo":
                        DBJournalInfo = JournalInfo()
                        if elem.find("NlmUniqueID") is not None:
                            DBJournalInfo.nlm_unique_id = elem.find("NlmUniqueID").text
                        if elem.find("Country") is not None:
                            DBJournalInfo.country = elem.find("Country").text
                        """#MedlineTA is just a name for the journal as an abbreviation
                        Abstract with PubMed-ID 21625393 has no MedlineTA attributebut it has to be set in PostgreSQL, that is why "unknown" is inserted instead. There is just a <MedlineTA/> tag and the same information is given in  </JournalIssue> <Title>Biotechnology and bioprocess engineering : BBE</Title>, but this is not (yet) read in this parser -> line 173:
                        """
                        if elem.find("MedlineTA") is not None and elem.find("MedlineTA").text is None:
                            DBJournalInfo.medline_ta = "unknown"
                        elif elem.find("MedlineTA") is not None:
                            DBJournalInfo.medline_ta = elem.find("MedlineTA").text
                        DBCitation.journal_infos = [DBJournalInfo]

                    if elem.tag == "CitationSubset":
                        DBCitation.citation_subsets = []
                        for subelem in elem:
                            DBCitationSubset = CitationSubset(subelem.text)
                            DBCitation.citation_subsets.append(DBCitationSubset)

                    if elem.tag == "MeshHeadingList":
                        DBCitation.meshheadings = []
                        DBCitation.qualifiers = []
                        for mesh in elem:
                            DBMeSHHeading = MeshHeading()
                            mesh_desc = mesh.find("DescriptorName")
                            if mesh_desc is not None:
                                DBMeSHHeading.descriptor_name = mesh_desc.text
                                DBMeSHHeading.descriptor_name_major_yn = mesh_desc.attrib["MajorTopicYN"]
                                DBMeSHHeading.descriptor_ui = mesh_desc.attrib["UI"]
                            if mesh.find("QualifierName") is not None:
                                mesh_quals = mesh.findall("QualifierName")
                                for qual in mesh_quals:
                                    DBQualifier = Qualifier()
                                    DBQualifier.descriptor_name = mesh_desc.text
                                    DBQualifier.qualifier_name = qual.text
                                    DBQualifier.qualifier_name_major_yn = qual.attrib["MajorTopicYN"]
                                    DBQualifier.qualifier_ui = qual.attrib["UI"]
                                    DBCitation.qualifiers.append(DBQualifier)
                            DBCitation.meshheadings.append(DBMeSHHeading)

                    if elem.tag == "GrantList":
                        # catch KeyError in case there is no CompleteYN attribute before committing DBCitation
                        try:
                            DBCitation.grant_list_complete_yn = elem.attrib["CompleteYN"]
                        except Exception:
                            pass
                        DBCitation.grants = []
                        for grant in elem:
                            DBGrants = Grant()

                            # grantid is restricted to 200 characters
                            if grant.find("GrantID") is not None and grant.find("GrantID").text is not None:
                                temp_grantid = grant.find("GrantID").text
                                if len(temp_grantid) < 200:
                                    DBGrants.grantid = temp_grantid
                                else:
                                    DBGrants.grantid = temp_grantid[0:197] + "..."

                            if grant.find("Acronym") is not None:
                                DBGrants.acronym = grant.find("Acronym").text

                            # agency is restricted to 200 characters
                            if grant.find("Agency") is not None and grant.find("Agency").text is not None:
                                temp_agency = grant.find("Agency").text
                                if len(temp_agency) < 200:
                                    DBGrants.agency = temp_agency
                                else:
                                    DBGrants.agency = temp_agency[0:197] + "..."

                            if grant.find("Country") is not None:
                                DBGrants.country = grant.find("Country").text

                            DBCitation.grants.append(DBGrants)

                    if elem.tag == "DataBankList":
                        # catch KeyError in case there is no CompleteYN attribute before committing DBCitation
                        try:
                            DBCitation.data_bank_list_complete_yn = elem.attrib["CompleteYN"]
                        except Exception:
                            pass
                        DBCitation.accessions = []
                        DBCitation.databanks = []

                        all_databanks = []
                        all_acc_numbers = {}

                        for databank in elem:
                            temp_name = databank.find("DataBankName").text
                            # check unique data_bank_name per PubMed ID and not null
                            if temp_name is not None and temp_name not in all_databanks:
                                DBDataBank = DataBank()
                                DBDataBank.data_bank_name = temp_name
                                DBCitation.databanks.append(DBDataBank)
                                all_databanks.append(temp_name)
                                all_acc_numbers[temp_name] = []

                            acc_numbers = databank.find("AccessionNumberList")

                            if acc_numbers is not None and temp_name is not None:
                                for acc_number in acc_numbers:
                                    # check unique accession number per PubMed ID and data_bank_name
                                    if acc_number.text not in all_acc_numbers[temp_name]:
                                        DBAccession = Accession()
                                        DBAccession.data_bank_name = DBDataBank.data_bank_name
                                        DBAccession.accession_number = acc_number.text
                                        DBCitation.accessions.append(DBAccession)
                                        all_acc_numbers[temp_name].append(acc_number.text)

                    if elem.tag == "Language":
                        DBLanguage = Language()
                        DBLanguage.language = elem.text
                        DBCitation.languages = [DBLanguage]

                    if elem.tag == "PublicationTypeList":
                        DBCitation.publication_types = []
                        all_publication_types = []
                        for subelem in elem:
                            # check for unique elements in PublicationTypeList
                            if subelem.text not in all_publication_types:
                                DBPublicationType = PublicationType()
                                DBPublicationType.publication_type = subelem.text
                                DBCitation.publication_types.append(DBPublicationType)
                                all_publication_types.append(subelem.text)

                    if elem.tag == "Article":
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

                    if elem.tag == "VernacularTitle":
                        DBCitation.vernacular_title = elem.tag

                    if elem.tag == "OtherAbstract":
                        DBOtherAbstract = OtherAbstract()
                        DBCitation.other_abstracts = []
                        for other in elem:
                            if other.tag == "AbstractText":
                                DBOtherAbstract.other_abstract = other.text
                        DBCitation.other_abstracts.append(DBOtherAbstract)

                    if elem.tag == "OtherID":
                        DBCitation.other_ids = []
                        DBOtherID = OtherId()
                        if len(elem.text) < 80:
                            DBOtherID.other_id = elem.text
                        else:
                            DBOtherID.other_id = elem.text[0:77] + "..."
                        DBOtherID.other_id_source = elem.attrib["Source"]
                        DBCitation.other_ids.append(DBOtherID)

                    # start Kersten: some abstracts contain another structure - code changed:
                    # check for different labels: "OBJECTIVE", "CASE SUMMARY", ...
                    # next 3 lines are unchanged
                    if elem.tag == "Abstract":
                        DBAbstract = Abstract()
                        DBCitation.abstracts = []
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
                                                list(child_AbstractText.items())[0][1]
                                                + ":\n"
                                                + child_AbstractText.text
                                                + "\n"
                                            )
                                    # label and NlmCategory - take label - first index has to be one:
                                    if len(list(child_AbstractText.items())) == 2:
                                        temp_abstract_text += (
                                            list(child_AbstractText.items())[1][1]
                                            + ":\n"
                                            + child_AbstractText.text
                                            + "\n"
                                        )
                        # if there is only one AbstractText-Tag ("usually") - no labels used:
                        if elem.find("AbstractText") is not None and len(elem.findall("AbstractText")) == 1:
                            temp_abstract_text = elem.findtext("AbstractText")
                        # append abstract text for later pushing it into db:
                        DBAbstract.abstract_text = temp_abstract_text
                        # next 3 lines are unchanged - some abstract texts (few) contain the child-tag "CopyrightInformation" after all AbstractText-Tags:
                        if elem.find("CopyrightInformation") is not None:
                            DBAbstract.copyright_information = elem.find("CopyrightInformation").text
                        DBCitation.abstracts.append(DBAbstract)
                    # end Kersten - code changed

                    """
                    #old code:
                    if elem.tag == "Abstract":
                        DBAbstract = PubMedDB.Abstract()
                        DBCitation.abstracts = []

                        if elem.find("AbstractText") is not None:   DBAbstract.abstract_text = elem.find("AbstractText").text
                        if elem.find("CopyrightInformation") is not None:   DBAbstract.copyright_information = elem.find("CopyrightInformation").text
                        DBCitation.abstracts.append(DBAbstract)
                    """
                    if elem.tag == "KeywordList":
                        # catch KeyError in case there is no Owner attribute before committing DBCitation
                        try:
                            DBCitation.keyword_list_owner = elem.attrib["Owner"]
                        except Exception:
                            pass
                        DBCitation.keywords = []
                        all_keywords = []
                        for subelem in elem:
                            # some documents contain duplicate keywords which would lead to a key error - if-clause
                            if subelem.text not in all_keywords:
                                all_keywords.append(subelem.text)
                            else:
                                continue
                            DBKeyword = Keyword()
                            DBKeyword.keyword = subelem.text
                            # catch KeyError in case there is no MajorTopicYN attribute before committing DBCitation
                            try:
                                DBKeyword.keyword_major_yn = subelem.attrib["MajorTopicYN"]
                            except Exception:
                                pass

                            # null check for keyword
                            if DBKeyword.keyword is not None:
                                DBCitation.keywords.append(DBKeyword)

                    if elem.tag == "Affiliation":
                        if len(elem.text) < 2000:
                            DBCitation.article_affiliation = elem.text
                        else:
                            DBCitation.article_affiliation = elem.text[0:1996] + "..."

                    if elem.tag == "SupplMeshList":
                        DBCitation.suppl_mesh_names = []
                        for suppl_mesh in elem:
                            DBSupplMeshName = SupplMeshName()
                            if len(suppl_mesh.text) < 80:
                                DBSupplMeshName.suppl_mesh_name = suppl_mesh.text
                            else:
                                DBSupplMeshName.suppl_mesh_name = suppl_mesh.text[0:76] + "..."
                            DBSupplMeshName.suppl_mesh_name_ui = suppl_mesh.attrib["UI"]
                            DBSupplMeshName.suppl_mesh_name_type = suppl_mesh.attrib["Type"]
                            DBCitation.suppl_mesh_names.append(DBSupplMeshName)

            await db.commit()
            await db.connection.close()
        return True


def get_memory_usage(pid=os.getpid(), format="%mem"):
    """
    Get the Memory Usage from a specific process
    @pid = Process ID
    @format = % or kb (%mem or rss) ...
    """
    return float(os.popen("ps -p %d -o %s | tail -1" % (pid, format)).read().strip())


def _start_parser(path_and_check):
    """
    Used to start MultiProcessor Parsing
    """
    print(path_and_check, "\tpid:", os.getpid())
    asyncio.run(MedlineParser(path_and_check[0])._parse(path_and_check[1]))
    return path_and_check[1]


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


def run(medline_path, clean, start, end, processes):
    with sync_session.begin() as session:
        check_existing = session.query(Citation).count() > 0

    if end is not None:
        end = int(end)

    if clean:
        refresh_tables()
    paths = []
    for root, dirs, files in os.walk(medline_path):
        for filename in files:
            if os.path.splitext(filename)[-1] in [".xml", ".gz"]:
                paths.append(os.path.join(root, filename))
    paths.sort()

    pool = Pool(processes=processes)  # start with processors
    result = pool.map_async(
        _start_parser,
        [
            (
                path,
                check_existing,
            )
            for path in paths[start:end]
        ],
    )
    result.get()

    # without multiprocessing:
    # for path in paths:
    #    _start_parser(path)

    # with async
    # asyncio.run(gather_with_concurrency(10, *([MedlineParser(apath)._parse() for apath in paths[start:end]])))


if __name__ == "__main__":
    start = os.environ.get("PMPG_FILELIST_START", 0)
    end = os.environ.get("PMPG_FILELIST_END", None)
    processes = os.environ.get("PMPG_PROCESSES", 2)
    medline_path = os.environ.get("PMPG_MEDLINE_PATH", "data/xmls/")
    clean = str(os.environ.get("PMPG_CLEAN", False)).lower() == "true"

    print(f"Launching with {start=}, {end=}, {processes=}t, {medline_path=}, {clean=}")
    import sys

    sys.exit(0)
    # log start time of programme:
    start = time.asctime()
    run(medline_path, clean, int(start), end, int(processes))
    # end time programme
    end = time.asctime()

    print("############################################################")
    print(f"Programme started: {start} - ended: {end}")
    print("############################################################")
