### Table Tennis Match Matcher (TTMM/2T2M)

- **End users**: Table tennis/ping-pong players at university/town/community (from newbies and beginners to amateurs/advanced and professionals)
- **Problem**: Players would like to have more practice but waste much time searching a mate. Also, some want to practice with players of exact level or at exact time or with some other exact parameters
- **One-liner**: *Stop spamming all chats and find your perfect table tennis partner instantly*
- **Core features (why it works)**: matching algorithm, user profiles, search simplification with agent
- **Core functionality (by TA)**: publish your availability & parameters for match, set up configs for search, view matching partners. Important! Requests should consider only approving/declining; no chat implementation, but after approve, users share contacts with each other


### Implementation plan, version 1

- **Core feauture to be implemented**: User profiles
- **What exactly will be implemented**: Each player can create a profile, containing name, level, available time, and additional information, and insert own profile to a database. From the database, any user can list a list of players with all necessary information. If a user wills to play with other player, they can send a request to such player. 
- **Additional information**: only a database and user profile mechanisms will be implemented. For the version 1, no real-time notifications or search simplification are supposed.


### Implementation plan, version 2

- **Core features to be implemented**: Matching algorithm, LLM agent integration, and enhanced user experience
- **What exactly will be implemented**:
    - **Matching algorithm with filters**: In "Players" page, users can filter the list of players according to desired parameters. Such feature will be implemented by providing to user a range of filters, such as available time range, player's skill, and others. Users can also sort players and use the "Find Matches" button to discover suitable partners with a scoring algorithm.
    - **LLM agent integration**: Add AI chat to help users interact with the TTMM system via natural language prompts. The agent can search profiles, manage match requests, update profiles, and provide statistics through conversational interface. Works with any OpenAI-compatible LLM service (default: qwen-code-api).
    - **UI/UX enhancements**:
        - Add title attributes to buttons for better discoverability
        - Show request status visually (not sent/sent by you/sent to you/see contacts)
        - Improve players representation with card and table view options
        - Add exact time slots support (available at specific times, not just weekly)
    - **Profile enhancements**:
        - Add preferences field to profiles
        - Make profiles reviewable by a click
        - Auto-redirect to your profile after saving edits
        - Implement LLM-based content moderation to prevent inappropriate text in profile fields
    - **Authentication**: Implement OAuth (Google OAuth) for secure user authentication
