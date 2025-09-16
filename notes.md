## YC

YC link: https://www.ycombinator.com/jobs/role/software-engineer

Company Name class: .flex.flex-col.items-start.gap-y-1 span.block

Job Title class: .flex.flex-col.items-start.gap-y-1 .text-sm.font-semibold.leading-tight.text-linkColor

Get link code:

link_elem = driver.find_element(By.CSS_SELECTOR, ".flex.flex-col.items-start.gap-y-1 .text-sm.font-semibold.leading-tight.text-linkColor a")
url = link_elem.get_attribute("href")

Get Logo code:

Array.from(document.querySelectorAll(".h-8.w-8.rounded-full.md\\:h-16.md\\:w-16"))
  .map(el => el.getAttribute("src"));