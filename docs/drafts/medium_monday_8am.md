# The 8am Rush Doesn't Show Up in the Missed-Call Rate

*An average of 491,832 calls in two hours on an ordinary Monday, 1.63 times the rest of the week. Fewer than half answered live. The queue didn't shrink. It moved.*

[CARD: docs/drafts/cards/card_medium_preview_1400x788.png — hero image under the subtitle; set as the story's preview image]

---

Somewhere in England, at a minute past eight on a Monday morning, someone is pressing redial.

They might be calling about a child's temperature that didn't come down overnight, or a repeat prescription that ran out on Saturday. They might be calling because the weekend gave them time to notice something they've been ignoring. We don't know, and the data never will. What we can know is that they aren't alone, and that the line they're waiting on is busier at that moment than at almost any other time in the week.

Everyone who has rung a GP surgery knows the 8am rush. NHS England now measures it. Since October 2025 it has published monthly data from the cloud-based phone systems most practices use: every inbound call to participating practices, by practice, by day, by two-hour time band. For August 2026 it says that 2,037,943 calls, 7.5% of the month's total, were made between 8am and 10am on Monday mornings.

I wanted to know whether that number holds up. So I built a pipeline to rebuild it from the raw files, then asked what it was really measuring.

## The number is right. The picture is not quite.

The first thing to say is that NHS England's figure is correct. I summed every practice's Monday calls in the 08:00–10:00 band across all five Mondays in August and got 2,037,943 exactly.

Five Mondays. That's where it gets interesting.

August 2026 had one more Monday than most months, and the last of them, 31 August, was the Summer Bank Holiday. Most surgeries close on bank holidays. The phones still rang, 70,616 times between 8am and 10am, but that's a fraction of a normal Monday. The headline adds four ordinary Mondays and one bank holiday together and reports the total as a share of the month.

The obvious way to read "7.5% of calls in two hours on Monday" is as a measure of the Monday peak. It isn't, quite. It depends on how many Mondays a month has and whether one of them is a holiday. A month with four ordinary Mondays and no bank holiday would give a different share for exactly the same pattern of demand.

So I separated them. On the four ordinary Mondays, an average of 491,832 calls reached GP practices between 8am and 10am. That's about 246,000 an hour.

On an ordinary Tuesday to Friday, the same two hours averaged 302,158.

Same practices. Same phone systems. Same two hours.

Monday is 1.63 times busier.

And it's concentrated. On an ordinary Monday, 28.7% of the whole day's calls arrive in those first two hours.

[CHART: docs/charts/week_heatmap_2026-08.png — average inbound calls per hour, weekday × time band]

There's a quieter inconsistency in the publication itself. Two of its other headline figures, inbound calls in core hours and inbound calls between 8am and 10am, exclude the bank holiday. The Monday figure includes it. Neither choice is wrong on its own. But within one release, the same day is counted in one headline and left out of the next. If you're putting these numbers side by side in a board paper, that's worth knowing.

## A third of calls are neither answered nor missed

The headline outcomes are clear enough. In August 2026, 57.7% of inbound calls were answered by practice staff and 10.4% were missed, a figure that includes voicemail.

Add those up and you get 68.1%. What happened to the rest?

They split two ways. 25.3% ended in the automated menu, the "press 1 for prescriptions" stage, before the caller joined a queue. NHS England counts these as "dealt with". Its guidance says that "may be" because the caller was signposted to another service, checked an existing appointment or was pointed to another route such as an online form. The same category also covers a caller who simply "decides to end the call after listening to an information message". The data can't say which happened. Another 6.6% became callback requests, where the system holds the caller's place in the queue and rings them back. 99.6% of those callbacks are made.

So nearly a third of calls don't end in a live conversation at the moment they're made, yet none of them count as failures. Some of those callers got what they needed from the menu; some gave up there. That isn't a scandal. It's a description of how modern phone systems work. But it changes what "57.7% answered" means. It isn't 57.7% of patients who got through and 42.3% who didn't.

How much a practice relies on its menu varies widely: among practices with at least 500 calls, the middle 80% ended between 13.6% and 34.3% of calls there. Practices configure their systems differently, which is why NHS England warns against comparing them directly.

## The queue didn't shrink. It moved.

Those national shares hide when things happen. So I split every outcome by day and two-hour band.

Look at the missed-call rate alone and 8am on a Monday looks easier to get through than the middle of the morning. On an ordinary Monday, 11.1% of calls between 8am and 10am were missed. Between 10am and noon, it was 12.8%.

The busiest two hours of the week have a lower missed-call rate than the two hours after. The reason is where the queue went.

Between 8am and 10am on an ordinary Monday, only 48.7% of calls were answered when they were made, the only stretch of the working day below half. Another 14.5% became callback requests. For the rest of that Monday, callback requests never went above 8.8%. More calls ended in the automated menu too: 25.7%, against 18.6% between 10am and noon.

So the queue didn't shrink at 8am. It moved, into callbacks and into the menu. A system that offers a callback holds your place and rings you back, and 99.6% of those calls are made. That's better than an engaged tone. But it means the 8am rush barely shows in the missed-call rate.

Tuesday to Friday has the same shape, less sharply: 59.8% answered and 9.7% callback requests between 8am and 10am, against 65.8% and 5.8% from 10am to noon.

[CHART: docs/charts/outcomes_by_time_band_2026-08.png — outcome of inbound calls by time band, ordinary Monday against Tuesday to Friday]

One caution. Practices set up their queues and callbacks differently, so this describes the national mix of phone systems, not how any single surgery handles its morning.

## Who isn't in the data

Here's the part I didn't expect.

The publication covers 5,327 of 6,171 open practices, 86.3%. Weight that by registered patients and coverage is 87.5%. Put the other way, about 7.9 million patients are registered at practices whose calls aren't in the figures.

The easy assumption is that those practices opted out. Almost none did. 7.8 million of those patients are at practices that agreed to take part but whose phone supplier isn't yet sending data. This is a plumbing gap, not a refusal.

It isn't spread evenly, though. I matched practices to OHID's 2025 practice-level deprivation score (all but 77 of the 6,171 have one; how it's built isn't documented, which I come back to below) and split practices into five equal groups.

The most deprived fifth has the lowest coverage: 83.4%. The other four fifths range from 86.5% to 90.7%.

The obvious objection is geography. Deprivation clusters by region, and some regions are less covered. North East and Yorkshire, for instance, is at 81.3%. So I checked within regions. If the most deprived practices had the same coverage as the less deprived practices in their own region, they'd be at about 86.9%. They're at 83.4%. Region explains part of the gap, not all of it. Most of what's left is in the North West, where the most deprived practices are 8.4 points less covered than their neighbours, and the Midlands, at 7.4. North East and Yorkshire runs the other way: there, the most deprived practices are better covered than their neighbours.

[CHART: docs/charts/coverage_by_deprivation_2026-08.png — patient coverage by deprivation quintile]

This is a data gap, not an access gap. These practices may answer their phones perfectly well. But the national figures, the ones quoted in briefings and press releases, speak slightly less for patients in the most deprived areas than for anyone else.

That matters because those practices look different. Where we do have their data, the most deprived fifth received 28.7 calls per 1,000 patients per working day, against 22.1 in the least deprived fifth. I can't tell you why from this data. It might be need, or the way practices in those areas use the phone versus other routes, or something else entirely. So does the gap distort the national picture? I checked. If every deprivation fifth were counted in proportion to its full population, calls per 1,000 patients per working day would rise from 24.49 to 24.58, about 0.4%. The skew barely moves the national rate. What it changes is whose experience the figures describe.

## What the data cannot tell you

This dataset is published as official statistics in development, and NHS England is open about its limits. So should I be.

It counts calls, not people. One person who rings eleven times before getting through is eleven calls. The Monday rush is partly redial, and nothing here can separate a busy morning from a few determined callers.

It doesn't say why anyone called, who answered, or what happened next. An answered call isn't an appointment.

Missed calls include voicemail. For some practices, voicemail is the prescription line, so a "missed" call may be a request that was dealt with.

Wait-time figures have a break in June 2026. One supplier corrected how it measured waiting time, and earlier months weren't restated. Any trend in "answered within two minutes" across that point compares two different measurements.

The practice deprivation score's method isn't stated in its metadata. The usual approach weights the neighbourhoods a practice's patients live in rather than its own postcode, and I've assumed that. If it's wrong, the deprivation groups describe where practices are rather than who they serve.

And the summer dip, from between 26.8 and 28.3 calls per 1,000 patients per working day between October and June, to 24.3 in July and 24.5 in August, rests on one summer. It looks seasonal. I can't prove that yet.

## How I checked it

The pipeline follows the same Bronze → Silver → Gold pattern as my other projects: eleven monthly releases, about 77 million rows, joined to registered-patient lists, the national practice register and the deprivation scores. Every downloaded file is fingerprinted, and every publication page is saved as it read on the day.

Before Gold says anything new, it has to rebuild NHS England's own figures. For August 2026 I checked 49. 43 matched, every count exactly and every percentage to the precision published, including all 310 cells of the national day-by-time table. Two were explained: the registered-patient totals are 0.03% short, and the gap sits in 42 practices with no row in the 1 August list.

The other four were labelled wrongly. From the January 2026 edition onward, the call-duration percentages are printed one row out of place, so the figure labelled "1 minute or less: 8.3%" is really the share over five minutes. The true share under a minute is 22.8%. The gate also showed that November 2025 was revised upward after publication, by 29,234 calls, without its practice-level files being reissued.

None of this is dramatic. It's the kind of thing you only find if you check.

The code, the reconciliation table and every figure in this piece are on GitHub: [github.com/YusufIsmailayo/nhs-gp-cloud-telephony-pipeline](https://github.com/YusufIsmailayo/nhs-gp-cloud-telephony-pipeline). Clone it, run three notebooks, and you'll get the same numbers.

## Back to the redial

So, the person pressing redial at a minute past eight on a Monday.

Theirs is one of roughly a quarter of a million calls in that hour, and fewer than half of them will be answered there and then. The phone system they're calling may end their call in a menu, offer them a callback, or put them in a queue, and each of those counts differently in the national figures. If their practice is in one of the most deprived parts of the North West or the Midlands, there's a better than usual chance their call isn't counted at all.

None of that tells us whether they got what they needed. But it does tell us where the 8am rush goes when it isn't answered. Not into the missed-call rate, which barely moves, but into a queue that rings back. For about one in seven of those calls, the next ring will be the practice calling back.

---

*Data: NHS England, Cloud Based Telephony Data in General Practice (October 2025 – August 2026); NHS England, Patients Registered at a GP Practice (1 August 2026); ODS practice register; OHID Fingertips, practice deprivation score (IMD 2025). All figures reproducible from the repository above.*
