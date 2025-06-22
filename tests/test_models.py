from phlux.models import Company
from phlux.scraping import load_company_data


def test_load_company_data():
    companies = load_company_data("companies.csv")
    assert companies, "No companies loaded"
    assert isinstance(companies[0], Company)
    first = companies[0]
    assert first.name and first.link and first.selector

