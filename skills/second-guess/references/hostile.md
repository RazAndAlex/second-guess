# Hostile simulated people

Used in step 4 of `SKILL.md`. Each person is told to look for reasons this idea fails. They are simulated by an AI, and they stand in for no real person. What they say shows what to ask real people.

## 1. Choose the people

Always simulate these three buying roles. Give each one a concrete job in this idea's world.

- **The person who pays:** holds the money this would come from.
- **The person who uses it:** has to change a daily habit to use it.
- **The person who can block it:** can say no without paying or using. Examples: a head of IT, a regulator, a shop's category manager, a spouse, an app store reviewer.

If one person both pays and uses, as with many home products, keep both prompts. The first looks at the money and the second at the habit.

Add up to three more, whichever fit this idea:

- **The person on a substitute:** happy with what they do today, a name from step 1.
- **The rival:** runs a competitor found in step 1 and is planning a reply.
- **The person next door:** close to the target group, and has never had this problem.

Every person counts the same. Give them no weights, no scores and no votes.

## 2. Tailor each person

Fill these from the idea and from step 1. Generic people give generic objections, so make each detail belong to this idea.

- Role and job, in this idea's world. Use no real person's name.
- What they use or do today. Use the competitors and substitutes you found.
- What burned them before, in this line of work.
- What they care about most.

Describe the idea neutrally, with its plain features. Leave out your own arguments for it.

## 3. Run each person

Give each person a fresh start, with no tools, so one answer cannot shape the next:

- Claude Code: the `Agent` tool, one call per person.
- Codex: one subagent per person.
- Anywhere else: `claude -p --tools "" "PROMPT"`, one call per person.
- If the harness cannot remove a helper's tools, write "use no tools" in the prompt.
- If none of these starts, write each person yourself, one at a time. Finish one before you begin the next.

The prompt:

```
You are role-playing as ROLE AND JOB.
You use or do this today: TODAY.
This burned you before: BURNED.
You care most about: CARES.

Here is a product idea: IDEA, DESCRIBED NEUTRALLY.
These alternatives exist: COMPETITORS AND SUBSTITUTES, IN WORDS.

Look for reasons this fails, from where you sit. You have seen ideas like this
come and go. Stay in character and speak plainly.

Answer with two things:
1. The one thing most likely to kill this idea, and why, from your own work.
2. The one question to ask a real person in your job that would show whether
   you are right. Ask what that person did in the past. Leave out what they
   would do in the future.

Write in words only: no digits, no amounts of money, no percentages, no counts,
no fractions. Say nothing about how many people would buy.
```

## 4. Rank by severity, in words

Read all the answers. Merge objections that say the same thing, and keep the people's words where you can. Then rank them, most severe first. Start each `kills` text with one of these words:

- **Fatal:** if this is true, the idea cannot work as described.
- **Serious:** the idea works only after a large change.
- **Minor:** a real cost that the idea can survive.

The order in the file and the word at the start are the whole ranking. They are your judgement, so write them as words, with no number or chart.

## 5. Write the file

Write `attack-draft.json` in the run folder. It holds 1 to 20 findings, with exactly these keys:

- `person`: who said it.
- `kills`: the severity word, then what could kill the idea.
- `ask`: the question to ask real people.

This example is made up, and shows the shape only:

```json
{"findings": [
  {"person": "The person who can block it, a category manager at a garden chain",
   "kills": "Fatal: my shelves go to products with a sales record, and this has none.",
   "ask": "The last time you listed a product from a new brand, what did you ask to see first?"},
  {"person": "The person who uses it, a weekend gardener",
   "kills": "Serious: I already water by looking at the soil, and I have never wanted an app for it.",
   "ask": "When did you last lose a plant to bad watering, and what did you change after that?"},
  {"person": "The person who pays, the same gardener at the till",
   "kills": "Minor: batteries are one more thing to remember.",
   "ask": "What did you stop using last season, and why?"}
]}
```

## What the program refuses

`attack` refuses any money amount, any purchase percentage and phrases such as "would buy" or "will pay". Later, `report` checks this same text for numbers, so a figure here blocks the report unless a passing card holds it.

The safe way is to use no figures at all:

- Write "a low price" and leave out the amount.
- Write "several shop managers", and leave out number words such as "three".
- Avoid "half", "a third", "dozens", "twice" and "double". "A third party" is refused too, so write "an outside company".
- "One" is allowed.
- Avoid "will pay". Write "nobody has a budget for this".

## Credit

The persona fields (role, background, traits), the opening "You are role-playing as", the mix of skeptics and people outside the target group, and the rule to describe the idea neutrally are adapted from Althing, https://github.com/DataViking-Tech/Althing. So is the `claude -p --tools ""` way of calling a harness with tools off.

Copyright (c) 2026 DataViking Tech. Used under the MIT License.
