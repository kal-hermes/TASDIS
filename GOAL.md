I'm thinking of creating a game to learn and practice system design.
The way it works is that the user will pretend to be at system design job interview, and the interviewer will be role-played by an LLM. The interviewer LLM will give ask the user to design a system chosen from a problem bank, initially in vague terms. The user then must ask the right questions and go through the right steps to come up with the design. You have access to a `system-design` skill so you would know. Roughly, the user needs to do the following steps:

1. Ask the interviewer LLM some questions to understand the constraints and use cases;
2. Come up with an abstract design;
3. Design the core components;
4. Understand the bottlenecks;
5. Scale the design.

In the process, the user may do back-of-the-envelop calculations, and the interviewer LLM needs to verify that it makes sense. There are multiple ways in which the user can express the back-of-the-envelop calculation:
- hand-write the calculations and then submit them as image files (the interviewer will need to use vision to extract the calculations before analyzing them);
- compose the calculations in some unambiguous notation (I don't know what notations would be suitable. MathJax? LaTeX? It's not enough that the equations be rendered nicely; it needs to be easy for the LLM to understand);
- describe the calculations in prose only.
The user may complement the calculations with explanation in prose.

When making the actual system design, the user has three options:
- hand-draw design diagrams and submit them as image files;
- compose the design diagrams in a diagramming language and submit it as a file. Is Mermaid.js suitable?
- describe the design in prose only, instead of having any diagram.
The user may complement the diagrams with explanation in prose.

Depending on the way the user submitted the work, the interviewer LLM may provide feedback to match the original mode:
- image editing (use image editing software or an image editing model)
- add comments to (Mermaid.js) diagrams
- prose

The interviewer LLM will then grade the solution. Criteria to consider:
- Is the process correct? Has the user gone through the 5 steps? It's OK if the user revisits some steps, I think, because that's part of iterative engineering.
- Is the design correct?
- What has the user missed?

The interviewer LLM will then provide final feedback to the user.

There is a learning mode and a testing mode to the mock interview:
- in learning mode, the user may ask for help from the LLM, in which case the LLM will start by giving hints, and then full-blown explanations and hand-holding if the user needs them.
- in testing mode, the user cannot get any help the LLM: the LLM will simply refuse to give any hint.

Also, there is a setting to impose or remove platform constraints:
- unconstrained: the user may pick any cloud provider and tech stack to base their solution on;
- constrained: the interviewer LLM will demand that the solution use a particular cloud provider and particular tech stack (e.g. "must be using AWS, MySQL, and RabbitMQ")

Ideally, during evaluation of the solution, you must take into account whether it is realistic. Handwaving components of the system with unrealistic, unverifiable performance and behaviour characteristics is not acceptable. E.g. if the user claims that they will use "a storage system that has a 5 petabytes per second throughput", obviously that's bullshit. A much better answer would be "S3 because it supports up to 2,700 MB/s and 3,500 files/s, with latency well below 100ms"

Implement as a browser game.
- User would be looking at the browser windows as though they are facing the interviewer.
- pixel art from the 8-bit or 16-bit consoles era, animated
- provide an area to display images, diagrams, and maybe equations directly in the game.
- To make the game more fun, the interview settings can be changed:
  - A Klingon or a Vulcan as the interviewer
  - A pirate of the Caribbean as the interviewer
  - A Texan cowboy as the interviewer
  - An actual, normal tech interviewer
- Make the settings match the intervier; e.g. for the Texan cowboy, the background is a ranch and the text responses must be like how a Texan cowboy speaks.
- Create gibberish sound effects to match the interviewer when they speak.
- Since we're working with LLMs, you need to provide a settings dialog where the user can specify the LLM providers and models, and optional API keys.
  - text
  - vision
  - image generation or editing
- i18n - support English, French, Simplified Chinese (Mandarin), Traditional Chinese (Candonese or Taiwanese).
