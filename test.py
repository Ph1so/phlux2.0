from phlux.scraping import get_jobs_headless

# print(get_jobs_headless(name="Duolingo", url="https://careers.duolingo.com/#careers", instructions="CLICK:button[aria-haspopup='listbox']->CSS:#web-ui11 [role='option']", headless=False))
print(get_jobs_headless(name = "Optiver" , url = "https://optiver.com/working-at-optiver/career-opportunities/page/2/?search=internship&_gl=1*rb345g*_gcl_au*Mjk2MDM5OTE1LjE3NDg5MTM5ODQ.&numberposts=10&level=internship&paged=1" , instructions="CLICK:'Load more'->CSS:h5", headless=False))