"""M20: the fake name sets for measuring the redactor's name recall. Not a test file itself.

Every name here is FAKE (invented combinations; no well-known person's full name). These sets
were committed BEFORE any names list existed, so the held-out set N2 can't have been tuned to.
  CONTEXTS     8 window-title shapes a name appears in
  N1           68 names: the set measured in the M20 plan (61% recall with spaCy alone)
  N2           40 held-out names: rarer names and other spellings, never used to build the list
  N2_CAPS      8 of N2 in ALL CAPS (part of N2's score)
  LOWERCASE    names typed in lower case: measured and reported, not required (a known gap)
  N3           ordinary lines whose words are also names: precision (festival lines reported apart)
  CUE_PHRASES  ordinary lines with "with / by / call / from / hi..." in them: precision
A name counts as caught when every word of it with 2+ letters is masked (a lone initial identifies nobody).
"""

CONTEXTS = ["{n}", "Chat with {n}", "Call {n}", "{n} - WhatsApp", "Meeting with {n} at 10:30",
            "{n} resume.pdf - Adobe Acrobat", "Re: Leave request from {n} - Gmail", "Assignment submitted by {n}"]

N1 = {
    "Hindi belt": ["Amit Sharma", "Pooja Gupta", "Rajesh Kumar", "Sunita Yadav", "Neha Verma", "Deepak Chauhan",
                   "Kavita Singh", "Saurabh Mishra", "Shubham Pandey", "Aarti Joshi", "Vikas Srivastava"],
    "Telugu": ["Venkata Ramana", "Srinivas Rao", "Lakshmi Prasanna", "Sai Kiran Reddy", "Durga Prasad", "Bhargav Naidu",
               "Harsha Vardhan", "Yashwanth Chowdary", "Sravani Kolli", "Naveen Gaddam", "Chaitanya Varma", "Swathi Konda"],
    "Tamil, Kannada, Malayalam": ["Karthik Subramanian", "Divya Ramesh", "Senthil Kumar", "Meenakshi Sundaram",
                                  "Manjunath Gowda", "Anoop Nair", "Sreeja Menon", "Arun Pillai"],
    "other regions": ["Riya Chatterjee", "Sachin Patil", "Snehal Deshpande", "Gurpreet Singh", "Harleen Kaur",
                      "Mohammed Asif", "Ayesha Siddiqui", "Farhan Qureshi", "Nikhil Jain", "Rohan Fernandes"],
    "initials": ["S. Ramesh", "K. Venkatesh", "R. Lakshmi", "M.S. Reddy", "Ramesh S.", "A. Kumar", "T. Srinivas", "B. Swathi"],
    "first name only": ["Ramesh", "Priya", "Sneha", "Venkatesh", "Lakshmi", "Bhargav", "Sravani", "Aditya", "Pooja", "Imran"],
    "transliterations": ["Sreenivas Rao", "Shrinivas Kulkarni", "Laxmi Devi", "Chaithanya Reddy", "Vyshnavi Kolla",
                         "Sourabh Dixit", "Raghvendra Bhat", "Swati Joshi", "Venkatesa Murthy"],
}

N2 = {
    "Telugu": ["Bhanu Prakash", "Sowmya Vadlamudi", "Tirupathi Rao Kollu", "Keerthana Boddu", "Mallikarjun Pothula",
               "Anusha Tadikonda", "Prudhvi Chintala", "Hima Bindu Gorantla"],
    "Hindi belt": ["Abhishek Tripathi", "Shweta Agarwal", "Rakesh Bhardwaj", "Monika Rawat", "Vivek Saxena",
                   "Anjali Rastogi", "Pankaj Dwivedi"],
    "Tamil, Kannada, Malayalam": ["Thirumalai Selvam", "Kavya Ranganathan", "Gopalakrishnan Iyengar", "Nandini Hegde",
                                  "Shreyas Kamath", "Aswathy Kurup", "Vishnu Namboothiri"],
    "other regions": ["Debashish Mukherjee", "Tanushree Ghosh", "Omkar Kulkarni", "Rutuja Bhosale", "Jaspreet Gill",
                      "Zoya Ansari", "Tanveer Shaikh", "Lalremruata Hmar", "Bikash Gogoi", "Prerna Thakur"],
    "initials": ["V. Raghavan", "P. Madhavi", "G.K. Murthy", "Ananya R."],
    "first name only": ["Harini", "Tejaswini", "Dinesh", "Pranav"],
}
N2_CAPS = [name.upper() for name in ["Sowmya Vadlamudi", "Abhishek Tripathi", "Kavya Ranganathan", "Omkar Kulkarni",
                                     "Zoya Ansari", "V. Raghavan", "Harini", "Bikash Gogoi"]]

LOWERCASE = ["amit sharma", "pooja", "srinivas rao", "sneha reddy", "karthik", "venkatesh iyer"]

N3_ORDINARY = ["RAM usage 80%", "Dev server on port 5173", "Ruby on Rails guide", "Jasmine tests passing",
               "Prime Video - Google Chrome", "Hope this helps - Gmail", "Mark as read", "Bill payment due",
               "Will update tomorrow", "Grace period ends", "Sunny weather today", "Rose Pine theme - Visual Studio Code",
               "Joy of coding", "Amber alert settings", "Summer sale ends Friday", "Amar Chitra Katha comics",
               "Raja Rani serial episode 5"]
N3_FESTIVALS = ["Durga Puja holidays", "Lakshmi Pooja timings", "Krishna Janmashtami holiday"]  # masked: fail closed

CUE_PHRASES = ["Sign in with Google", "Built with React", "Powered by Vercel", "Call Center hours", "Meeting with Team Alpha",
               "Re: Leave request from HR - Gmail", "Assignment submitted by Group 4", "Shared by Google Drive",
               "Welcome to Notion", "Back to Settings", "Chat with Support", "Hi Team, standup notes",
               "Dear Customer - Gmail", "Export to PDF", "Sort by Date Modified", "Connect with GitHub"]


def names(group_dict: dict) -> list[str]:
    return [name for group in group_dict.values() for name in group]
