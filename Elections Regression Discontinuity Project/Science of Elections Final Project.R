# to run, highlight everything and run selected
library(tidyverse)
library(haven)
library(readxl)
library(crosswalkr)
library(stargazer)
library(estimatr)
library(AER)
library(rdd)

# download data on gub elections
# from https://dataverse.harvard.edu/dataset.xhtml?persistentId=hdl:1902.1/20408
govs <- read_xlsx("/Users/noah/Desktop/Harris/Year 2/Q1/Science of Elections/Final Project polls/StateElections_Gub_2012_09_06_Public_Version.xlsx")

# drop nas - disregarding undefined or exentuating elections
govs_invest <- govs %>%
  drop_na(gub_election)

#creating column after_elect to mark the year after an election, so I can
#look for changes in party

govs_invest <- govs_invest %>%
  filter(year >= 1968) %>%
  mutate(after_elect = ifelse(lag(gub_election)==1, 1, 0)) %>% 
  relocate(after_elect, .after = gub_election)

govs_invest <- govs_invest %>%
  relocate(govparty_a, .before = gub_election)

govs_invest <- govs_invest %>%
  select(state, year, govparty_a, gub_election, after_elect, 
         gub_party_change, party_midyear_change_direction, 
         years_since_other_party, open_bcs_term_limit, govname1)

# download state pol election returns data
# from https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/DRSACA 
load("~/Desktop/Harris/Year 2/Q1/Science of Elections/Final Project polls/102slersuoacontest20181024-1.RData")
data <- table

# get the reps/dems makeup of state houses/senates by year  
data_invest <- data %>%
  group_by(year, state, sen) %>%
  summarise(reps = sum(rwin * eseats),
            dems = sum(dwin * eseats))

data_invest <- data_invest %>% 
  order(state)

# put both senate and house composition into house rows, 
# and filter out senate rows
data_invest <- data_invest %>%
  group_by(year, state) %>%
  mutate(sen_rep = case_when(sen == 1 ~ .1,
                             sen == 0 ~ lead(reps)),
         sen_dem = case_when(sen ==1 ~ .1,
                             sen == 0 ~ lead(dems))) %>%
  filter(sen == 0) %>%
  rename(house_dem = dems, house_rep = reps)

# get rid of senate/house dummy column to get just
# year, state, and house  dems/reps
data_invest <- data_invest %>%
  select(-sen)

# Add columns for change in seat numbers from previous year
data_invest <- data_invest %>%
  group_by(state) %>%
  mutate(change_house_rep = house_rep - lag(house_rep),
         change_house_dem = house_dem - lag(house_dem),
         change_sen_rep = sen_rep - lag(sen_rep),
         change_sen_dem = sen_dem - lag(sen_dem)) 

# Merge gub data with state pol data
data_total <- merge(x=data_invest,y=govs_invest,by=c("year", "state"),all=TRUE)

# remove the 5 states that have a 4 year state house/sen term: Alabama, Louisiana, 
# Maryland, Mississippi and North Dakota. 

total_clean <- data_total %>%
  filter(state != c("Alabama", "Louisiana", "Maryland", 
                    "Mississippi", "North Dakota")) %>%
  arrange(state)

# remove elections with a governor who changed parties mid-term
total_clean <- total_clean %>%
  mutate(party_midyear_change_direction = ifelse(is.na(party_midyear_change_direction) == TRUE,
                                                 0, party_midyear_change_direction)) %>%
  filter(party_midyear_change_direction == 0)

# creating a variable to code for if the governorship's party changed from rep to dem (0),
# dem to rep (1), did not change (2), or changed from a non-major party or is
# currently a non-major party (-9). 

total_clean <- total_clean %>%
  mutate(elec_change_gov_party = case_when(lag(govparty_a) - govparty_a == -1 ~ 0,
                                           lag(govparty_a) - govparty_a == 1 ~ 1,
                                           lag(govparty_a) - govparty_a == 0 ~ 2,
                                           TRUE ~ -9))

total_clean <- total_clean %>%
  relocate(elec_change_gov_party, .after = govparty_a)

# filtering out -9 (non-major party govs)

total_clean <- total_clean %>%
  filter(elec_change_gov_party != -9)

# Now I'm left with a column (elec_change_gov_party) that tells me if the govs party 
# changed in the year previous, and what direction that was. We also still have 
# years_since_other_party, a count variable saying 1) how many years the Democrats 
# have been in power (expressed by a positive number) or 2) how many years the 
# Republicans have been in power (multiplied by -1). When there has been an independent, 
# zeros are entered.  


# filter for only the years in which governorship changes party -- with this
# I can find the state house elections following to see what changes in seats occurred
# this is a list of the data for the years of the elections -- if there is not a house/sen
# election the same year as the gov election, there will be NAs in those columns.
only_change <- total_clean %>%
  filter(elec_change_gov_party != 2) # intermediate output

# here I read in the gov_sen_house_totals dataset from class in order to get vote totals
# for the governors elections that I find in only_change

govs_votes_raw <- read_csv('/Users/noah/Desktop/Harris/Year 2/Q1/Science of Elections/Final Project polls/gov_sen_house_totals.csv')

# Filter for gub elections after 1968 (to match other data)
govs_votes_raw <- govs_votes_raw %>%
  filter(year > 1968,
         office == 'G')

# create vote margin column for each state-year pair (which is an election)
# keep governors name and party, too. Use non-major parties to create
# vote margins, then drop them from df.
govs_votes_raw <- govs_votes_raw %>%
  group_by(state, year) %>%
  filter(!is.na(vote_g)) %>% # get rid of elections w/ an unknown vote total
  summarize(vote_margin = vote_g / sum(vote_g),
            name = name,
            party = party,
            winner = max(vote_margin), # get winner dummy to run Fuzzy Rd
            winner = ifelse(vote_margin == winner, 1, 0),
            winner = as.factor(winner)) %>%
  filter(party == 'D' | party == 'R')

# get dem subset
govs_votes_dem <- govs_votes_raw %>%
  filter(party == 'D')

# crosswalk state names for abbreviations
# from https://statisticsglobe.com/state-name-abbreviation-r
govs_votes_dem <- govs_votes_dem %>%
  mutate(state = state.name[grep(state, state.abb)])

# now merge everything
total_clean_votes_dem <- merge(x = total_clean, y = govs_votes_dem, by = c('state', 'year'), all.x = TRUE)

sum(is.na(total_clean_votes_dem$winner))

# shrink df to only relevant cols
graphing_data_dem <- total_clean_votes_dem %>%
  select(year, state, change_house_dem, 
         elec_change_gov_party, govname1, vote_margin, winner)

# vote margins are a year behind because I merged on year not govname - fixing now
# setting vote_margin equal to itself two spaces prior, to put margin on same line
# as next election

graphing_data_dem <- graphing_data_dem %>%
  group_by(state) %>%
  mutate(vote_margin = lag(vote_margin, 2),
         winner = lag(winner, 2))

# checking for NAs - should be about a quarter not NA
sum(is.na(graphing_data_dem$vote_margin))
length(graphing_data_dem$vote_margin)

graphing_data_dem <- graphing_data_dem %>%
  drop_na(vote_margin)

# maybe I can actually plot this?
# subsetting  a reasonably small bandwidth
graphing_data_subset_dem <- graphing_data_dem %>%
  subset(vote_margin < .54 & vote_margin > .46)


# checking for NAs in the change column - looks ok
sum(is.na(graphing_data_subset_dem$change_house_dem))
length(graphing_data_subset_dem$change_house_dem)
# 16 NAs out of 160 - leaves me with 144, should be ok

# plotting
ggplot(graphing_data_subset_dem, aes(vote_margin, change_house_dem, color = winner)) +
  geom_point() + 
  geom_smooth(data = filter(graphing_data_subset_dem, vote_margin <= .5), method = "lm") +
  geom_smooth(data = filter(graphing_data_subset_dem, vote_margin > .5), method = "lm") +
  geom_vline(xintercept=0.5, linetype="longdash") +
  ggtitle("The Effect of A Democrat Winning the \nGovernor's Mansion on Democratic \nState House Membership Levels") +
  xlab("Democratic Vote Margin") +
  ylab("Change in Democratic State House Members") +
  scale_colour_discrete(h = c(100, 230) + 15,
                        c = 70,
                        l = 60, name="Winner or\nLoser",
                        breaks=c("0", "1"), labels=c("Loser", "Winner")) +
  theme(plot.title = element_text(hjust = 0.5))

# Does not appear to be an effect distinguishable from 0

# now we arrange the data for modeling:

model_data_dem <- graphing_data_subset_dem %>%
  mutate(treat = as.integer(winner),
         cen_vote_margin = vote_margin - .5,
         above_c = vote_margin >= .5, 
         inter = treat * cen_vote_margin,
         state = as.factor(state))

# cen_vote_margin gives us the slope below the cutoff and inter gives us 
# the slope above the cutoff.

# first stage is significant
stargazer(lm(treat ~ above_c, data = model_data_dem), type='text')

# do the 2SLS
stargazer(ivreg(change_house_dem ~ vote_margin | treat,
              data = model_data_dem), title = 'Effects of Dem Candidate Vote Margins on Dem State House Delegation', type = 'text', out = 'fit_dem_basic.html')
stargazer(ivreg(change_house_dem ~ vote_margin + state | state + treat,
                data = model_data_dem), title = 'Effects of Dem Candidate Vote Margins on Dem State House Delegation w/ Fixed Effects', omit = 'state', type='text', out = 'fit_dem_fe.html')

# there is not a relationship that can be distinguished from 0 -- for Dems...

###======================================================================================

# try again with Reps
govs_votes_rep <- govs_votes_raw %>%
  filter(party == 'R')

# crosswalk state names for abbreviations
# from https://statisticsglobe.com/state-name-abbreviation-r
govs_votes_rep <- govs_votes_rep %>%
  mutate(state = state.name[grep(state, state.abb)])

# now merge everything
total_clean_votes_rep <- merge(x = total_clean, y = govs_votes_rep, by = c('state', 'year'), all.x = TRUE)

# shrink df to only relevant cols
graphing_data_rep <- total_clean_votes_rep %>%
  select(year, state, change_house_rep, 
         elec_change_gov_party, govname1, vote_margin, winner)

# vote margins are a year behind because I merged on year not govname - fixing now
# setting vote_margin equal to itself two spaces prior, to put margin on same line
# as next election

graphing_data_rep <- graphing_data_rep %>%
  group_by(state) %>%
  mutate(vote_margin = lag(vote_margin, 2),
         winner = lag(winner, 2))

# checking for NAs - should be about a quarter not NA
sum(is.na(graphing_data_rep$vote_margin))
length(graphing_data_rep$vote_margin)

graphing_data <- graphing_data_rep %>%
  drop_na(vote_margin)

# maybe I can actually plot this?
# subsetting  a reasonably small bandwidth
graphing_data_subset_rep <- graphing_data_rep %>%
  subset(vote_margin < .54 & vote_margin > .46) 

# how many nas...
sum(is.na(graphing_data_subset_rep$change_house_rep))
length(graphing_data_subset_rep$change_house_rep)
# missing 17 out of 200 -- leaves me with 183, fine

ggplot(graphing_data_subset_rep, aes(vote_margin, change_house_rep, color = winner)) +
  geom_point() + 
  geom_smooth(data = filter(graphing_data_subset_rep, vote_margin <= .5), method = "lm") +
  geom_smooth(data = filter(graphing_data_subset_rep, vote_margin > .5), method = "lm") +
  geom_vline(xintercept=0.5, linetype="longdash") +
  ggtitle("The Effect of A Republican Winning the \nGovernor's Mansion on Republican \nState House Membership Levels") +
  xlab("Republican Vote Margin") +
  ylab("Change in Republican State House\nMembership in Next Election") +
  scale_colour_discrete(h = c(230, 270) + 15,
                        c = 85,
                        l = 65, name="Winner or\nLoser",
                        breaks=c("0", "1"), labels=c("Loser", "Winner")) +
theme(plot.title = element_text(hjust = 0.5))

# Doesn't seem to be any effect

# now we arrange the data for modeling:
model_data_rep <- graphing_data_subset_rep %>%
  mutate(treat = as.integer(winner),
         cen_vote_margin = vote_margin - .5, 
         above_c = vote_margin >= .5,
         below_c = vote_margin < .5,
         inter = treat * cen_vote_margin,
         state = as.factor(state))

# cen_vote_margin would give us the slope below the cutoff and inter gives us 
# the slope above the cutoff.

# First stage is significant
stargazer(lm(treat ~ above_c, data=model_data_rep), type='text')

# Here's the 2SLS
stargazer(ivreg(change_house_rep ~ vote_margin | treat,
              data = model_data_rep), title = 'Effects of Rep Candidate Vote Margins on Rep State House Delegation', type = 'text', out = 'fit_rep_basic.html') # not significant

stargazer(ivreg(change_house_rep ~ vote_margin + state | state + treat,
              data = model_data_rep), omit = 'state', 
          title = 'Effects of Rep Candidate Vote Margins on Rep State House Delegation w/ Fixed Effects', 
          type = 'text', out = 'fit_rep_fe.html') # not significant
