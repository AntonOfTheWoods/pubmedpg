# -*- coding: UTF-8 -*-

from sqlalchemy import Column, Date, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import backref, relationship

from pubmedpg.db.base import Base

"""
    This script creates tables in the PostgreSQL schema pubmed. The basic setup of tables and columns is based on:
    http://biotext.berkeley.edu/code/medline-schema/medline-schema-perl-oracle.sql

    Build tables, classes, and mappings
    http://www.nlm.nih.gov/bsd/licensee/elements_descriptions.html
"""

OWNER_ENUM = Enum("NLM", "NASA", "PIP", "KIE", "HSR", "HMD", "SIS", "NOTNLM", name="owner")
STATUS_ENUM = Enum(
    "In-Data-Review",
    "In-Process",
    "MEDLINE",
    "OLDMEDLINE",
    "PubMed-not-MEDLINE",
    "Publisher",
    "Completed",
    name="status",
)
YESNO_ENUM = Enum("Y", "N", "y", "n", name="yesno")


class Citation(Base):
    pmid = Column(Integer, nullable=False, primary_key=True)
    date_created = Column(Date)
    date_completed = Column(Date, index=True)
    date_revised = Column(Date, index=True)
    number_of_references = Column(Integer, default=0)
    keyword_list_owner = Column(OWNER_ENUM)
    citation_owner = Column(OWNER_ENUM, default="NLM")
    citation_status = Column(STATUS_ENUM)
    article_title = Column(String(4000), nullable=False)
    start_page = Column(String(10))
    end_page = Column(String(10))
    medline_pgn = Column(String(200))
    article_affiliation = Column(String(2000))
    article_author_list_comp_yn = Column(YESNO_ENUM, default="Y")
    data_bank_list_complete_yn = Column(YESNO_ENUM, default="Y")
    grant_list_complete_yn = Column(YESNO_ENUM, default="Y")
    vernacular_title = Column(String(4000))

    def __repr__(self):
        return f"PubMed-ID: {self.pmid}\n\tArticle Title: {self.article_title.encode('utf-8')}%s\n"


class PmidFileMapping(Base):
    pmid = Column(
        ForeignKey("citation.pmid", deferrable=True, initially="DEFERRED", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    id_file = Column(
        ForeignKey("xml_file.id", deferrable=True, initially="DEFERRED", ondelete="CASCADE", onupdate="CASCADE"),
    )

    def __repr__(self):
        return f"PmidFileMapping({self.pmid}, {self.id_file})"


class XmlFile(Base):
    id = Column(Integer, nullable=False, autoincrement=True, primary_key=True)
    xml_file_name = Column(String(50), nullable=False, unique=True)
    doc_type_name = Column(String(100))
    dtd_public_id = Column(String(200))  # ,   nullable=False)
    dtd_system_id = Column(String(200))  # ,   nullable=False)
    time_processed = Column(DateTime())

    def __repr__(self):
        return f"XmlFile({self.xml_file_name}, {self.doc_type_name}, {self.dtd_system_id}, {self.time_processed})"

    citation = relationship(
        Citation, secondary=PmidFileMapping.__table__, backref=backref("xml_files", order_by=xml_file_name)
    )


class Journal(Base):
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

    def __repr__(self):
        return "Journal ({}, {}, {}, {}, {}, {}, {}, {}, {}, {})".format(
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

    citation = relationship(Citation, backref=backref("journals", order_by=issn, cascade="all, delete-orphan"))


class JournalInfo(Base):
    pmid = Column(
        ForeignKey("citation.pmid", deferrable=True, initially="DEFERRED", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    nlm_unique_id = Column(String(20), index=True)
    medline_ta = Column(String(200), nullable=False, index=True)
    country = Column(String(50))

    def __repr__(self):
        return f"JournalInfo ({self.nlm_unique_id}, {self.medline_ta}, {self.country})"

    citation = relationship(
        Citation, backref=backref("journal_infos", order_by=nlm_unique_id, cascade="all, delete-orphan")
    )


class Abstract(Base):
    pmid = Column(
        ForeignKey("citation.pmid", deferrable=True, initially="DEFERRED", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    abstract_text = Column(Text)
    copyright_information = Column(String(2000))

    def __repr__(self):
        return f"Abstract: ({self.copyright_information}) \n\n{self.abstract_text}"

    citation = relationship(Citation, backref=backref("abstracts", order_by=pmid, cascade="all, delete-orphan"))


class Chemical(Base):
    pmid = Column(
        ForeignKey("citation.pmid", deferrable=True, initially="DEFERRED", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    registry_number = Column(String(20), nullable=False, primary_key=True)
    name_of_substance = Column(String(3000), nullable=False, index=True, primary_key=True)
    substance_ui = Column(String(10), index=True)

    def __repr__(self):
        return f"Chemical ({self.registry_number}, {self.name_of_substance})"

    citation = relationship(
        Citation, backref=backref("chemicals", order_by=registry_number, cascade="all, delete-orphan")
    )


class CitationSubset(Base):
    pmid = Column(
        ForeignKey("citation.pmid", deferrable=True, initially="DEFERRED", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    citation_subset = Column(String(500), nullable=False, primary_key=True)

    def __repr__(self):
        return f"CitationSubset ({self.citation_subset})"

    citation = relationship(
        Citation, backref=backref("citation_subsets", order_by=citation_subset, cascade="all, delete-orphan")
    )


class Comment(Base):
    id = Column(Integer, primary_key=True)
    pmid = Column(
        ForeignKey("citation.pmid", deferrable=True, initially="DEFERRED", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    ref_type = Column(String(21), nullable=False)
    ref_source = Column(String(255), nullable=False)
    pmid_version = Column(Integer, index=True)

    def __repr__(self):
        return f"Comment ({self.pmid}, {self.ref_type}, {self.ref_source}, {self.pmid_version})"

    citation = relationship(Citation, backref=backref("comments", order_by=ref_source, cascade="all, delete-orphan"))


class GeneSymbol(Base):
    pmid = Column(
        ForeignKey("citation.pmid", deferrable=True, initially="DEFERRED", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    gene_symbol = Column(
        String(40), nullable=False, index=True, primary_key=True
    )  # a bug in one medlin entry causes an increase to 40, from 30

    def __repr__(self):
        return f"GeneSymbol ({self.gene_symbol})"

    citation = relationship(
        Citation, backref=backref("gene_symbols", order_by=gene_symbol, cascade="all, delete-orphan")
    )


class MeshHeading(Base):
    pmid = Column(
        ForeignKey("citation.pmid", deferrable=True, initially="DEFERRED", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    descriptor_name = Column(String(500), primary_key=True)
    descriptor_name_major_yn = Column(YESNO_ENUM, default="N")
    descriptor_ui = Column(String(10), index=True)

    def __repr__(self):
        return f"MeshHeading ({self.descriptor_name}, {self.descriptor_name_major_yn})"

    citation = relationship(
        Citation, backref=backref("meshheadings", order_by=descriptor_name, cascade="all, delete-orphan")
    )


class Qualifier(Base):
    pmid = Column(
        ForeignKey("citation.pmid", deferrable=True, initially="DEFERRED", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    descriptor_name = Column(String(500), index=True, primary_key=True)
    qualifier_name = Column(String(500), index=True, primary_key=True)
    qualifier_name_major_yn = Column(YESNO_ENUM, default="N")
    qualifier_ui = Column(String(10), index=True)

    def __repr__(self):
        return f"Qualifier ({self.descriptor_name}, {self.qualifier_name}, {self.qualifier_name_major_yn})"

    citation = relationship(
        Citation, backref=backref("qualifiers", order_by=qualifier_name, cascade="all, delete-orphan")
    )


class PersonalName(Base):
    id = Column(Integer, primary_key=True)
    pmid = Column(
        ForeignKey("citation.pmid", deferrable=True, initially="DEFERRED", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
    )
    last_name = Column(String(300), nullable=False, index=True)
    fore_name = Column(String(100))
    initials = Column(String(10))
    suffix = Column(String(20))

    def __repr__(self):
        return f"PersonalName ({self.last_name}, {self.fore_name}, {self.initials}, {self.suffix})"

    citation = relationship(
        Citation, backref=backref("personal_names", order_by=last_name, cascade="all, delete-orphan")
    )


class OtherAbstract(Base):
    pmid = Column(
        ForeignKey("citation.pmid", deferrable=True, initially="DEFERRED", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    other_abstract = Column(Text)
    #    other_abstract_id            = Column(String(30), nullable=False)
    #    other_abstract_source     = Column(String(20), nullable=False)

    def __repr__(self):
        return f"OtherAbstract ({self.pmid}, {self.other_abstract})"

    # __table_args__ = (
    #     CheckConstraint("other_id_source IN ('NASA', 'KIE', 'PIP', 'POP', 'ARPL', 'CPC', 'IND', 'CPFH', 'CLML', 'IM', 'SGC', 'NLM', 'NRCBL', 'QCIM', 'QCICL')", name='ck1_other_ids'),
    # )
    citation = relationship(Citation, backref=backref("other_abstracts", order_by=pmid, cascade="all, delete-orphan"))


class OtherId(Base):
    pmid = Column(
        ForeignKey("citation.pmid", deferrable=True, initially="DEFERRED", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    other_id = Column(String(200), nullable=False, index=True, primary_key=True)
    other_id_source = Column(String(10), nullable=False)

    def __repr__(self):
        return f"OtherID ({self.pmid}, {self.other_id})"

    citation = relationship(Citation, backref=backref("other_ids", order_by=pmid, cascade="all, delete-orphan"))


class Keyword(Base):
    pmid = Column(
        ForeignKey("citation.pmid", deferrable=True, initially="DEFERRED", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    keyword = Column(String(500), nullable=False, index=True, primary_key=True)
    keyword_major_yn = Column(YESNO_ENUM, default="N")

    def __repr__(self):
        return f"Keyword ({self.keyword}, {self.keyword_major_yn})"

    citation = relationship(Citation, backref=backref("keywords", order_by=keyword, cascade="all, delete-orphan"))


class SpaceFlight(Base):
    pmid = Column(
        ForeignKey("citation.pmid", deferrable=True, initially="DEFERRED", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    space_flight_mission = Column(String(500), nullable=False, primary_key=True)

    def __repr__(self):
        return f"SpaceFlight ({self.space_flight_mission})"

    citation = relationship(
        Citation, backref=backref("space_flights", order_by=space_flight_mission, cascade="all, delete-orphan")
    )


class Investigator(Base):
    id = Column(Integer, primary_key=True)
    pmid = Column(
        ForeignKey("citation.pmid", deferrable=True, initially="DEFERRED", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
    )
    last_name = Column(String(300), index=True)
    fore_name = Column(String(100))
    initials = Column(String(10))
    suffix = Column(String(20))
    investigator_affiliation = Column(String(200))

    def __repr__(self):
        return "Investigator ({}, {}, {}, {}, {})".format(
            self.last_name,
            self.fore_name,
            self.initials,
            self.suffix,
            self.investigator_affiliation,
        )

    citation = relationship(
        Citation, backref=backref("investigators", order_by=last_name, cascade="all, delete-orphan")
    )


class Note(Base):
    pmid = Column(
        ForeignKey("citation.pmid", deferrable=True, initially="DEFERRED", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    general_note = Column(String(2000), nullable=False, primary_key=True)
    general_note_owner = Column(OWNER_ENUM)

    def __repr__(self):
        return f"Keyword ({self.general_note}, {self.general_note_owner})"

    citation = relationship(Citation, backref=backref("notes", order_by=pmid, cascade="all, delete-orphan"))


class Author(Base):
    id = Column(Integer, primary_key=True)
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

    def __repr__(self):
        return f"Author ({self.last_name}, {self.fore_name}, {self.initials}, {self.suffix}, {self.collective_name})"

    citation = relationship(Citation, backref=backref("authors", order_by=last_name, cascade="all, delete-orphan"))


class Language(Base):
    pmid = Column(
        ForeignKey("citation.pmid", deferrable=True, initially="DEFERRED", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    language = Column(String(50), nullable=False, primary_key=True)

    def __repr__(self):
        return f"Language ({self.language})"

    citation = relationship(Citation, backref=backref("languages", order_by=language, cascade="all, delete-orphan"))


class DataBank(Base):
    pmid = Column(
        ForeignKey("citation.pmid", deferrable=True, initially="DEFERRED", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    data_bank_name = Column(String(300), nullable=False, primary_key=True)

    def __repr__(self):
        return f"DataBank ({self.data_bank_name})"

    citation = relationship(
        Citation, backref=backref("databanks", order_by=data_bank_name, cascade="all, delete-orphan")
    )


class Accession(Base):
    pmid = Column(
        ForeignKey("citation.pmid", deferrable=True, initially="DEFERRED", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    data_bank_name = Column(String(300), nullable=False, index=True, primary_key=True)
    accession_number = Column(String(100), nullable=False, index=True, primary_key=True)

    def __repr__(self):
        return f"Accession ({self.data_bank_name}, {self.accession_number})"

    citation = relationship(
        Citation, backref=backref("accessions", order_by=data_bank_name, cascade="all, delete-orphan")
    )


class Grant(Base):
    id = Column(Integer, primary_key=True)
    pmid = Column(
        ForeignKey("citation.pmid", deferrable=True, initially="DEFERRED", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    grantid = Column(String(200), index=True)
    acronym = Column(String(20))
    agency = Column(String(200))
    country = Column(String(200))

    def __repr__(self):
        return f"Grant ({self.grantid}, {self.acronym}, {self.agency}, {self.country})"

    citation = relationship(Citation, backref=backref("grants", order_by=grantid, cascade="all, delete-orphan"))


class PublicationType(Base):
    pmid = Column(
        ForeignKey("citation.pmid", deferrable=True, initially="DEFERRED", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    publication_type = Column(String(200), nullable=False, primary_key=True)

    def __repr__(self):
        return f"PublicationType ({self.publication_type})"

    citation = relationship(
        Citation, backref=backref("publication_types", order_by=publication_type, cascade="all, delete-orphan")
    )


class SupplMeshName(Base):
    pmid = Column(
        ForeignKey("citation.pmid", deferrable=True, initially="DEFERRED", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    suppl_mesh_name = Column(String(80), nullable=False, index=True, primary_key=True)
    suppl_mesh_name_ui = Column(String(10), nullable=False, index=True, primary_key=True)
    suppl_mesh_name_type = Column(String(8), nullable=False)

    def __repr__(self):
        return f"SupplMeshName ({self.suppl_mesh_name})"

    citation = relationship(
        Citation, backref=backref("suppl_mesh_names", order_by=suppl_mesh_name, cascade="all, delete-orphan")
    )
