# -*- coding: UTF-8 -*-

from sqlalchemy import CheckConstraint, Column, Date, DateTime, ForeignKey, ForeignKeyConstraint, Integer, String, Text
from sqlalchemy.orm import backref, relationship

from pubmedpg.db.base import Base

"""
    This script creates tables in the PostgreSQL schema pubmed. The basic setup of tables and columns is based on:
    http://biotext.berkeley.edu/code/medline-schema/medline-schema-perl-oracle.sql

    Build tables, classes, and mappings
    http://www.nlm.nih.gov/bsd/licensee/elements_descriptions.html
"""


class Citation(Base):
    pmid = Column(Integer, nullable=False, primary_key=True)
    date_created = Column(Date)
    date_completed = Column(Date, index=True)
    date_revised = Column(Date, index=True)
    number_of_references = Column(Integer, default=0)
    keyword_list_owner = Column(String(30))
    citation_owner = Column(String(30), default="NLM")
    citation_status = Column(String(50))
    article_title = Column(String(4000), nullable=False)
    start_page = Column(String(10))
    end_page = Column(String(10))
    medline_pgn = Column(String(200))
    article_affiliation = Column(String(2000))
    article_author_list_comp_yn = Column(String(1), default="Y")
    data_bank_list_complete_yn = Column(String(1), default="Y")
    grant_list_complete_yn = Column(String(1), default="Y")
    vernacular_title = Column(String(4000))

    # def __init__(self):
    #     self.pmid
    #     self.date_created
    #     self.date_completed
    #     self.date_revised
    #     self.number_of_references
    #     self.keyword_list_owner
    #     self.citation_owner
    #     self.citation_status
    #     self.article_title
    #     self.medline_pgn
    #     self.article_affiliation
    #     self.article_author_list_comp_yn
    #     self.data_bank_list_complete_yn
    #     self.grant_list_complete_yn
    #     self.vernacular_title

    def __repr__(self):
        # return "Citations: \n\tPMID: %s\n\tArticle Title: %s\n\tCreated: %s\n\tCompleted: %s" % (self.pmid, self.article_title, self.date_created, self.date_completed)
        return "PubMed-ID: %s\n\tArticle Title: %s\n" % (self.pmid, self.article_title.encode("utf-8"))

    __table_args__ = (
        CheckConstraint(
            "keyword_list_owner IN ('NLM', 'NASA', 'PIP', 'KIE', 'HSR', 'HMD', 'SIS', 'NOTNLM')",
            name="ck1_citation",
        ),
        CheckConstraint(
            "citation_owner IN ('NLM', 'NASA', 'PIP', 'KIE', 'HSR', 'HMD', 'SIS', 'NOTNLM')",
            name="ck2_citation",
        ),
        CheckConstraint(
            "citation_status IN ('In-Data-Review', 'In-Process', 'MEDLINE', 'OLDMEDLINE', 'PubMed-not-MEDLINE',"
            " 'Publisher', 'Completed')",
            name="ck3_citation",
        ),
        CheckConstraint("article_author_list_comp_yn IN ('Y', 'N', 'y', 'n')", name="ck4_citation"),
        CheckConstraint("data_bank_list_complete_yn IN ('Y', 'N', 'y', 'n')", name="ck5_citation"),
        CheckConstraint("grant_list_complete_yn IN ('Y', 'N', 'y', 'n')", name="ck6_citation"),
    )


class PmidFileMapping(Base):
    pmid = Column(
        ForeignKey("citation.pmid", deferrable=True, initially="DEFERRED", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    id_file = Column(Integer)
    xml_file_name = Column(String(50), nullable=False)
    # fk_pmid = Column(Integer, nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["id_file", "xml_file_name"],
            ["xml_file.id", "xml_file.xml_file_name"],
            onupdate="CASCADE",
            ondelete="CASCADE",
            name="fk3_pmids_in_file",
        ),
        # ForeignKeyConstraint(
        #     ["fk_pmid"],
        #     ["citation.pmid"],
        #     onupdate="CASCADE",
        #     ondelete="CASCADE",
        #     name="fk2_pmids_in_file",
        # ),
        # PrimaryKeyConstraint("fk_pmid"),
    )


class XmlFile(Base):

    id = Column(Integer, nullable=False, autoincrement=True, primary_key=True)
    xml_file_name = Column(String(50), nullable=False, primary_key=True)
    doc_type_name = Column(String(100))
    dtd_public_id = Column(String(200))  # ,   nullable=False)
    dtd_system_id = Column(String(200))  # ,   nullable=False)
    time_processed = Column(DateTime())

    # def __init__(self):
    #     self.id
    #     self.xml_file_name
    #     self.doc_type_name  # = doc_type_name
    #     self.dtd_system_id  # = dtd_system_id
    #     self.time_processed

    def __repr__(self):
        return "XMLFile(%s, %s, %s, %s)" % (
            self.xml_file_name,
            self.doc_type_name,
            self.dtd_system_id,
            self.time_processed,
        )

    citation = relationship(
        Citation, secondary=PmidFileMapping.__table__, backref=backref("xml_files", order_by=xml_file_name)
    )

    # __table_args__ = (PrimaryKeyConstraint("id", "xml_file_name"),)


class Journal(Base):
    # fk_pmid = Column(Integer, nullable=False, primary_key=True)
    pmid = Column(
        ForeignKey("citation.pmid", deferrable=True, initially="DEFERRED", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )

    issn = Column(String(30), index=True)
    issn_type = Column(String(30))
    volume = Column(String(200))
    issue = Column(String(200))
    pub_date_year = Column(Integer, index=True)
    pub_date_month = Column(String(20))
    pub_date_day = Column(String(2))
    medline_date = Column(String(40))
    title = Column(String(2000))
    iso_abbreviation = Column(String(100))

    # def __init__(self):
    #     self.issn
    #     self.issn_type
    #     self.volume
    #     self.issue
    #     self.pub_date_year
    #     self.pub_date_month
    #     self.pub_date_day
    #     self.medline_date
    #     self.title
    #     self.iso_abbreviation

    def __repr__(self):
        return "Journal (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)" % (
            self.issn,
            self.issn_type,
            self.volume,
            self.issue,
            self.pub_date_year,
            self.pub_date_month,
            self.pub_date_day,
            self.medline_date,
            self.title,
            self.iso_abbreviation,
        )

    # __table_args__ = (
    #     ForeignKeyConstraint(
    #         ["fk_pmid"], ["citation.pmid"], onupdate="CASCADE", ondelete="CASCADE"
    #     ),
    # )
    citation = relationship(Citation, backref=backref("journals", order_by=issn, cascade="all, delete-orphan"))


class JournalInfo(Base):
    # fk_pmid = Column(Integer, nullable=False, primary_key=True)
    pmid = Column(
        ForeignKey("citation.pmid", deferrable=True, initially="DEFERRED", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    nlm_unique_id = Column(String(20), index=True)
    medline_ta = Column(String(200), nullable=False, index=True)
    country = Column(String(50))

    # def __init__(self):
    #     self.nlm_unique_id
    #     self.medline_ta
    #     self.country

    def __repr__(self):
        return "JournalInfo (%s, %s, %s)" % (self.nlm_unique_id, self.medline_ta, self.country)

    # __table_args__ = (
    #     ForeignKeyConstraint(
    #         ["fk_pmid"],
    #         ["citation.pmid"],
    #         onupdate="CASCADE",
    #         ondelete="CASCADE",
    #         name="fk_medline_journal_info",
    #     ),
    # )
    citation = relationship(
        Citation, backref=backref("journal_infos", order_by=nlm_unique_id, cascade="all, delete-orphan")
    )


class Abstract(Base):

    # fk_pmid = Column(Integer, nullable=False)
    pmid = Column(
        ForeignKey("citation.pmid", deferrable=True, initially="DEFERRED", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    abstract_text = Column(Text)
    copyright_information = Column(String(2000))

    # def __init__(self):
    #     self.abstract_text
    #     self.copyright_information

    def __repr__(self):
        return "Abstract: (%s) \n\n%s" % (self.copyright_information, self.abstract_text)

    # __table_args__ = (
    #     ForeignKeyConstraint(
    #         ["fk_pmid"],
    #         ["citation.pmid"],
    #         onupdate="CASCADE",
    #         ondelete="CASCADE",
    #         name="fk_abstract",
    #     ),
    #     PrimaryKeyConstraint("fk_pmid"),
    # )
    citation = relationship(Citation, backref=backref("abstracts", order_by=pmid, cascade="all, delete-orphan"))


class Chemical(Base):
    # fk_pmid = Column(Integer, nullable=False)
    pmid = Column(
        ForeignKey("citation.pmid", deferrable=True, initially="DEFERRED", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    registry_number = Column(String(20), nullable=False, primary_key=True)
    name_of_substance = Column(String(3000), nullable=False, index=True, primary_key=True)
    substance_ui = Column(String(10), index=True)

    # def __init__(self):
    #     self.registry_number
    #     self.name_of_substance
    #     self.substance_ui

    def __repr__(self):
        return "Chemical (%s, %s)" % (self.registry_number, self.name_of_substance)

    # __table_args__ = (
    #     ForeignKeyConstraint(
    #         ["fk_pmid"],
    #         ["citation.pmid"],
    #         onupdate="CASCADE",
    #         ondelete="CASCADE",
    #         name="fk_chemical_list",
    #     ),
    #     PrimaryKeyConstraint("pmid", "registry_number", "name_of_substance"),
    # )
    citation = relationship(
        Citation, backref=backref("chemicals", order_by=registry_number, cascade="all, delete-orphan")
    )


class CitationSubset(Base):
    # fk_pmid = Column(Integer, nullable=False)
    pmid = Column(
        ForeignKey("citation.pmid", deferrable=True, initially="DEFERRED", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    citation_subset = Column(String(500), nullable=False, primary_key=True)
    # def __init__(self, citation_subset):
    #     self.citation_subset = citation_subset

    def __repr__(self):
        return "CitationSubset (%s)" % (self.citation_subset)

    # __table_args__ = (
    #     ForeignKeyConstraint(
    #         ["fk_pmid"],
    #         ["citation.pmid"],
    #         onupdate="CASCADE",
    #         ondelete="CASCADE",
    #         name="fk_citation_subsets",
    #     ),
    #     PrimaryKeyConstraint("pmid", "citation_subset"),
    # )
    citation = relationship(
        Citation, backref=backref("citation_subsets", order_by=citation_subset, cascade="all, delete-orphan")
    )


class Comment(Base):
    id = Column(Integer, primary_key=True)
    # fk_pmid = Column(Integer, nullable=False, index=True)
    pmid = Column(
        ForeignKey("citation.pmid", deferrable=True, initially="DEFERRED", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )

    ref_type = Column(String(21), nullable=False)
    ref_source = Column(String(255), nullable=False)
    pmid_version = Column(Integer, index=True)

    # def __init__(self):
    #     self.ref_type
    #     self.ref_source
    #     self.pmid_version

    def __repr__(self):
        return "Comment (%s, %s, %s, %s)" % (self.fk_pmid, self.ref_type, self.ref_source, self.pmid_version)

    # __table_args__ = (
    #     ForeignKeyConstraint(
    #         ["fk_pmid"],
    #         ["citation.pmid"],
    #         onupdate="CASCADE",
    #         ondelete="CASCADE",
    #         name="fk_comments_corrections",
    #     ),
    # )
    citation = relationship(Citation, backref=backref("comments", order_by=ref_source, cascade="all, delete-orphan"))


class GeneSymbol(Base):
    # fk_pmid = Column(Integer, nullable=False)
    pmid = Column(
        ForeignKey("citation.pmid", deferrable=True, initially="DEFERRED", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    gene_symbol = Column(
        String(40), nullable=False, index=True, primary_key=True
    )  # a bug in one medlin entry causes an increase to 40, from 30

    # def __init__(self):
    #     self.gene_symbol

    def __repr__(self):
        return "GeneSymbol (%s)" % (self.gene_symbol)

    # __table_args__ = (
    #     ForeignKeyConstraint(
    #         ["fk_pmid"],
    #         ["citation.pmid"],
    #         onupdate="CASCADE",
    #         ondelete="CASCADE",
    #         name="fk_gene_symbol_list",
    #     ),
    #     PrimaryKeyConstraint("fk_pmid", "gene_symbol"),
    # )
    citation = relationship(
        Citation, backref=backref("gene_symbols", order_by=gene_symbol, cascade="all, delete-orphan")
    )


class MeshHeading(Base):
    # fk_pmid = Column(Integer, nullable=False)
    pmid = Column(
        ForeignKey("citation.pmid", deferrable=True, initially="DEFERRED", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    descriptor_name = Column(String(500), primary_key=True)
    descriptor_name_major_yn = Column(String(1), default="N")
    descriptor_ui = Column(String(10), index=True)

    # def __init__(self):
    #     self.descriptor_name
    #     self.descriptor_name_major_yn
    #     self.descriptor_ui

    def __repr__(self):
        return "MeshHeading (%s, %s)" % (
            self.descriptor_name,
            self.descriptor_name_major_yn,
        )

    __table_args__ = (
        # ForeignKeyConstraint(
        #     ["fk_pmid"],
        #     ["citation.pmid"],
        #     onupdate="CASCADE",
        #     ondelete="CASCADE",
        #     name="fk_mesh_heading_list",
        # ),
        # PrimaryKeyConstraint("fk_pmid", "descriptor_name"),
        CheckConstraint("descriptor_name_major_yn IN ('Y', 'N', 'y', 'n')", name="ck1_mesh_heading_list"),
    )
    citation = relationship(
        Citation, backref=backref("meshheadings", order_by=descriptor_name, cascade="all, delete-orphan")
    )


class Qualifier(Base):
    # fk_pmid = Column(Integer, nullable=False)
    pmid = Column(
        ForeignKey("citation.pmid", deferrable=True, initially="DEFERRED", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    descriptor_name = Column(String(500), index=True, primary_key=True)
    qualifier_name = Column(String(500), index=True, primary_key=True)
    qualifier_name_major_yn = Column(String(1), default="N")
    qualifier_ui = Column(String(10), index=True)

    # def __init__(self):
    #     self.descriptor_name
    #     self.qualifier_name
    #     self.qualifier_name_major_yn
    #     self.qualifier_ui

    def __repr__(self):
        return "Qualifier (%s, %s, %s)" % (self.descriptor_name, self.qualifier_name, self.qualifier_name_major_yn)

    __table_args__ = (
        # ForeignKeyConstraint(
        #     ["fk_pmid"],
        #     ["citation.pmid"],
        #     onupdate="CASCADE",
        #     ondelete="CASCADE",
        #     name="fk_qualifier_names",
        # ),
        # PrimaryKeyConstraint("fk_pmid", "descriptor_name", "qualifier_name"),
        CheckConstraint("qualifier_name_major_yn IN ('Y', 'N', 'y', 'n')", name="ck2_qualifier_names"),
    )
    citation = relationship(
        Citation, backref=backref("qualifiers", order_by=qualifier_name, cascade="all, delete-orphan")
    )


class PersonalName(Base):
    id = Column(Integer, primary_key=True)
    # fk_pmid = Column(Integer, nullable=False)
    pmid = Column(
        ForeignKey("citation.pmid", deferrable=True, initially="DEFERRED", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
    )
    last_name = Column(String(300), nullable=False, index=True)
    fore_name = Column(String(100))
    initials = Column(String(10))
    suffix = Column(String(20))

    # def __init__(self):
    #     self.last_name
    #     self.fore_name
    #     self.initials
    #     self.suffix

    def __repr__(self):
        return "PersonalName (%s, %s, %s, %s)" % (self.last_name, self.fore_name, self.initials, self.suffix)

    # __table_args__ = (
    #     ForeignKeyConstraint(
    #         ["fk_pmid"],
    #         ["citation.pmid"],
    #         onupdate="CASCADE",
    #         ondelete="CASCADE",
    #         name="fk_personal_name_subject_list",
    #     ),
    # )
    citation = relationship(
        Citation, backref=backref("personal_names", order_by=last_name, cascade="all, delete-orphan")
    )


class OtherAbstract(Base):
    # fk_pmid = Column(Integer, nullable=False)
    pmid = Column(
        ForeignKey("citation.pmid", deferrable=True, initially="DEFERRED", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )

    #    other_abstract_id            = Column(String(30), nullable=False)
    #    other_abstract_source     = Column(String(20), nullable=False)
    other_abstract = Column(Text)

    # def __init__(self):
    #     #        self.other_abstract_id
    #     #        self.other_abstract_source
    #     self.other_abstract

    def __repr__(self):
        return "OtherAbstract (%s, %s)" % (self.fk_pmid, self.other_abstract)

    # __table_args__ = (
    #     ForeignKeyConstraint(
    #         ["fk_pmid"],
    #         ["citation.pmid"],
    #         onupdate="CASCADE",
    #         ondelete="CASCADE",
    #         name="fk_other_abstracts",
    #     ),
    #     PrimaryKeyConstraint("fk_pmid"),  # , 'other_id', 'other_id_source'),
    #     #        CheckConstraint("other_id_source IN ('NASA', 'KIE', 'PIP', 'POP', 'ARPL', 'CPC', 'IND', 'CPFH', 'CLML', 'IM', 'SGC', 'NLM', 'NRCBL', 'QCIM', 'QCICL')", name='ck1_other_ids'),
    # )
    citation = relationship(Citation, backref=backref("other_abstracts", order_by=pmid, cascade="all, delete-orphan"))


class OtherId(Base):
    # fk_pmid = Column(Integer, nullable=False)
    pmid = Column(
        ForeignKey("citation.pmid", deferrable=True, initially="DEFERRED", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    other_id = Column(String(200), nullable=False, index=True, primary_key=True)
    other_id_source = Column(String(10), nullable=False)

    # def __init__(self):
    #     self.other_id
    #     self.other_id_source

    def __repr__(self):
        return "OtherID (%s, %s)" % (self.fk_pmid, self.other_id)

    # __table_args__ = (
    #     ForeignKeyConstraint(
    #         ["fk_pmid"],
    #         ["citation.pmid"],
    #         onupdate="CASCADE",
    #         ondelete="CASCADE",
    #         name="fk_other_ids",
    #     ),
    #     PrimaryKeyConstraint("fk_pmid", "other_id"),
    # )
    citation = relationship(Citation, backref=backref("other_ids", order_by=pmid, cascade="all, delete-orphan"))


class Keyword(Base):
    # fk_pmid = Column(Integer, nullable=False)
    pmid = Column(
        ForeignKey("citation.pmid", deferrable=True, initially="DEFERRED", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    keyword = Column(String(500), nullable=False, index=True, primary_key=True)
    keyword_major_yn = Column(String(1), default="N")

    # def __init__(self):
    #     self.keyword
    #     self.keyword_major_yn

    def __repr__(self):
        return "Keyword (%s, %s)" % (self.keyword, self.keyword_major_yn)

    __table_args__ = (
        # ForeignKeyConstraint(
        #     ["fk_pmid"],
        #     ["citation.pmid"],
        #     onupdate="CASCADE",
        #     ondelete="CASCADE",
        #     name="fk_keyword_list",
        # ),
        # PrimaryKeyConstraint("fk_pmid", "keyword"),
        CheckConstraint("keyword_major_yn IN ('Y', 'N', 'y', 'n')", name="ck1_keyword_list"),
    )

    citation = relationship(Citation, backref=backref("keywords", order_by=keyword, cascade="all, delete-orphan"))


class SpaceFlight(Base):
    # fk_pmid = Column(Integer, nullable=False)
    pmid = Column(
        ForeignKey("citation.pmid", deferrable=True, initially="DEFERRED", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    space_flight_mission = Column(String(500), nullable=False, primary_key=True)

    # def __init__(self):
    #     self.space_flight_mission

    def __repr__(self):
        return "SpaceFlight (%s)" % (self.space_flight_mission)

    # __table_args__ = (
    #     ForeignKeyConstraint(
    #         ["fk_pmid"],
    #         ["citation.pmid"],
    #         onupdate="CASCADE",
    #         ondelete="CASCADE",
    #         name="fk_space_flight_missions",
    #     ),
    #     PrimaryKeyConstraint("fk_pmid", "space_flight_mission"),
    # )

    citation = relationship(
        Citation, backref=backref("space_flights", order_by=space_flight_mission, cascade="all, delete-orphan")
    )


class Investigator(Base):
    id = Column(Integer, primary_key=True)
    # fk_pmid = Column(Integer, nullable=False)
    pmid = Column(
        ForeignKey("citation.pmid", deferrable=True, initially="DEFERRED", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
    )
    last_name = Column(String(300), index=True)
    fore_name = Column(String(100))
    initials = Column(String(10))
    suffix = Column(String(20))
    investigator_affiliation = Column(String(200))

    # def __init__(self):
    #     self.last_name
    #     self.fore_name
    #     self.initials
    #     self.suffix
    #     self.investigator_affiliation

    def __repr__(self):
        return "Investigator (%s, %s, %s, %s, %s)" % (
            self.last_name,
            self.fore_name,
            self.initials,
            self.suffix,
            self.investigator_affiliation,
        )

    # __table_args__ = (
    #     ForeignKeyConstraint(
    #         ["fk_pmid"],
    #         ["citation.pmid"],
    #         onupdate="CASCADE",
    #         ondelete="CASCADE",
    #         name="fk_investigator_list",
    #     ),
    # )
    citation = relationship(
        Citation, backref=backref("investigators", order_by=last_name, cascade="all, delete-orphan")
    )


class Note(Base):
    # fk_pmid = Column(Integer, nullable=False)
    pmid = Column(
        ForeignKey("citation.pmid", deferrable=True, initially="DEFERRED", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )

    general_note = Column(String(2000), nullable=False, primary_key=True)
    general_note_owner = Column(String(20))

    # def __init__(self):
    #     self.general_note
    #     self.general_note_owner

    def __repr__(self):
        return "Keyword (%s, %s)" % (self.general_note, self.general_note_owner)

    __table_args__ = (
        # ForeignKeyConstraint(
        #     ["fk_pmid"],
        #     ["citation.pmid"],
        #     onupdate="CASCADE",
        #     ondelete="CASCADE",
        #     name="fk_general_notes",
        # ),
        # PrimaryKeyConstraint("fk_pmid", "general_note"),
        CheckConstraint("general_note_owner IN ('NLM', 'NASA', 'PIP', 'KIE', 'HSR', 'HMD', 'SIS', 'NOTNLM')"),
    )
    citation = relationship(Citation, backref=backref("notes", order_by=pmid, cascade="all, delete-orphan"))


class Author(Base):
    id = Column(Integer, primary_key=True)
    # fk_pmid = Column(Integer, nullable=False, index=True)
    pmid = Column(
        ForeignKey("citation.pmid", deferrable=True, initially="DEFERRED", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    last_name = Column(String(300), index=True)
    fore_name = Column(String(100))
    initials = Column(String(10))
    suffix = Column(String(20))
    collective_name = Column(String(2000), index=True)

    # def __init__(self):
    #     self.last_name
    #     self.fore_name
    #     self.initials
    #     self.suffix
    #     self.collective_name

    def __repr__(self):
        return "Author (%s, %s, %s, %s, %s)" % (
            self.last_name,
            self.fore_name,
            self.initials,
            self.suffix,
            self.collective_name,
        )

    # __table_args__ = (
    #     ForeignKeyConstraint(
    #         ["fk_pmid"],
    #         ["citation.pmid"],
    #         onupdate="CASCADE",
    #         ondelete="CASCADE",
    #         name="fk_author_list",
    #     ),
    # )
    citation = relationship(Citation, backref=backref("authors", order_by=last_name, cascade="all, delete-orphan"))


class Language(Base):
    # fk_pmid = Column(Integer, nullable=False)
    pmid = Column(
        ForeignKey("citation.pmid", deferrable=True, initially="DEFERRED", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    language = Column(String(50), nullable=False, primary_key=True)

    # def __init__(self):
    #     self.language

    def __repr__(self):
        return "Language (%s)" % (self.language)

    # __table_args__ = (
    #     ForeignKeyConstraint(
    #         ["fk_pmid"],
    #         ["citation.pmid"],
    #         onupdate="CASCADE",
    #         ondelete="CASCADE",
    #         name="fk_languages",
    #     ),
    #     PrimaryKeyConstraint("fk_pmid", "language"),
    # )
    citation = relationship(Citation, backref=backref("languages", order_by=language, cascade="all, delete-orphan"))


class DataBank(Base):
    # fk_pmid = Column(Integer, nullable=False)
    pmid = Column(
        ForeignKey("citation.pmid", deferrable=True, initially="DEFERRED", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    data_bank_name = Column(String(300), nullable=False, primary_key=True)

    # def __init__(self):
    #     self.data_bank_name

    def __repr__(self):
        return "DataBank (%s)" % (self.data_bank_name)

    # __table_args__ = (
    #     ForeignKeyConstraint(
    #         ["fk_pmid"],
    #         ["citation.pmid"],
    #         onupdate="CASCADE",
    #         ondelete="CASCADE",
    #         name="fk_data_bank_list",
    #     ),
    #     PrimaryKeyConstraint("fk_pmid", "data_bank_name"),
    # )
    citation = relationship(
        Citation, backref=backref("databanks", order_by=data_bank_name, cascade="all, delete-orphan")
    )


class Accession(Base):
    # fk_pmid = Column(Integer, nullable=False)
    pmid = Column(
        ForeignKey("citation.pmid", deferrable=True, initially="DEFERRED", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    data_bank_name = Column(String(300), nullable=False, index=True, primary_key=True)
    accession_number = Column(String(100), nullable=False, index=True, primary_key=True)

    # def __init__(self):
    #     self.data_bank_name
    #     self.accession_number

    def __repr__(self):
        return "Accession (%s, %s)" % (self.data_bank_name, self.accession_number)

    # __table_args__ = (
    #     ForeignKeyConstraint(
    #         ["fk_pmid"],
    #         ["citation.pmid"],
    #         onupdate="CASCADE",
    #         ondelete="CASCADE",
    #         name="fk_accession_number_list",
    #     ),
    #     PrimaryKeyConstraint("fk_pmid", "data_bank_name", "accession_number"),
    # )
    citation = relationship(
        Citation, backref=backref("accessions", order_by=data_bank_name, cascade="all, delete-orphan")
    )


class Grant(Base):
    id = Column(Integer, primary_key=True)
    # fk_pmid = Column(Integer, nullable=False, index=True)
    pmid = Column(
        ForeignKey("citation.pmid", deferrable=True, initially="DEFERRED", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    grantid = Column(String(200), index=True)
    acronym = Column(String(20))
    agency = Column(String(200))
    country = Column(String(200))

    # def __init__(self):
    #     self.grantid
    #     self.acronym
    #     self.agency
    #     self.country

    def __repr__(self):
        return "Grant (%s, %s, %s, %s)" % (self.grantid, self.acronym, self.agency, self.country)

    # __table_args__ = (
    #     ForeignKeyConstraint(
    #         ["fk_pmid"],
    #         ["citation.pmid"],
    #         onupdate="CASCADE",
    #         ondelete="CASCADE",
    #         name="fk_grant_list",
    #     ),
    # )
    citation = relationship(Citation, backref=backref("grants", order_by=grantid, cascade="all, delete-orphan"))


class PublicationType(Base):
    # fk_pmid = Column(Integer, nullable=False)
    pmid = Column(
        ForeignKey("citation.pmid", deferrable=True, initially="DEFERRED", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    publication_type = Column(String(200), nullable=False, primary_key=True)

    # def __init__(self):
    #     self.publication_type

    def __repr__(self):
        return "PublicationType (%s)" % (self.publication_type)

    # __table_args__ = (
    #     ForeignKeyConstraint(
    #         ["fk_pmid"],
    #         ["citation.pmid"],
    #         onupdate="CASCADE",
    #         ondelete="CASCADE",
    #         name="fk_publication_type_list",
    #     ),
    #     PrimaryKeyConstraint("fk_pmid", "publication_type"),
    # )
    citation = relationship(
        Citation, backref=backref("publication_types", order_by=publication_type, cascade="all, delete-orphan")
    )


class SupplMeshName(Base):
    # fk_pmid = Column(Integer, nullable=False)
    pmid = Column(
        ForeignKey("citation.pmid", deferrable=True, initially="DEFERRED", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    suppl_mesh_name = Column(String(80), nullable=False, index=True, primary_key=True)
    suppl_mesh_name_ui = Column(String(10), nullable=False, index=True, primary_key=True)
    suppl_mesh_name_type = Column(String(8), nullable=False)

    def __init__(self):
        self.suppl_mesh_name
        self.suppl_mesh_name_ui
        self.suppl_mesh_name_type

    def __repr__(self):
        return "SupplMeshName (%s)" % (self.suppl_mesh_name)

    # __table_args__ = (
    #     ForeignKeyConstraint(
    #         ["fk_pmid"],
    #         ["citation.pmid"],
    #         onupdate="CASCADE",
    #         ondelete="CASCADE",
    #         name="fk_suppl_mesh_name_list",
    #     ),
    #     PrimaryKeyConstraint("fk_pmid", "suppl_mesh_name", "suppl_mesh_name_ui"),
    # )
    citation = relationship(
        Citation, backref=backref("suppl_mesh_names", order_by=suppl_mesh_name, cascade="all, delete-orphan")
    )
