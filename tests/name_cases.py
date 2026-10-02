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
M21 (committed before any M21 measurement; N2 is spent, because M21's rule was designed after seeing its misses):
  N4           40 new held-out names, same groups as N2, chosen without checking indian_names.txt
  N4_CAPS      8 of N4 in ALL CAPS (part of N4's score); N4_LOWERCASE: reported only
  N5           ordinary lines where a listed first name is followed by a capitalized word (word-level cost, R10)
M22 (committed before any dataset was downloaded or measured; N4 is spent, it showed the list's limit):
  N6           40 new held-out names, same groups as N2/N4, chosen without checking any list or dataset
  N6_CAPS      8 of N6 in ALL CAPS (part of N6's score); N6_LOWERCASE: reported only
  O6           ordinary lines a big names list might over-mask (films, trains, temples, brands): word-level cost
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

N4 = {
    "Telugu": ["Jayaram Nidadavolu", "Sailaja Pemmasani", "Koteswara Rao Bandaru", "Lahari Chilukuri",
               "Nageswara Pasupuleti", "Pavithra Ganti", "Ramakrishna Mudunuri", "Srujana Velagapudi"],
    "Hindi belt": ["Ashutosh Kesarwani", "Nupur Maheshwari", "Devendra Bhadoria", "Kanchan Tomar", "Himanshu Lohani",
                   "Garima Nigam", "Rajkumar Kushwaha"],
    "Tamil, Kannada, Malayalam": ["Sivaraman Palaniappan", "Abirami Natarajan", "Kumaraswamy Hosamani",
                                  "Pallavi Bhandarkar", "Sreelakshmi Thampi", "Jithin Kuriakose", "Ananthu Pillai"],
    "other regions": ["Soumitra Bhowmik", "Ipsita Sengupta", "Chinmay Phadke", "Mrunal Kelkar", "Harshil Thakkar",
                      "Navneet Sekhon", "Shabnam Kazmi", "Arif Lakdawala", "Pranjal Saikia", "Biraj Mahapatra"],
    "initials": ["R. Kalaiselvi", "S.V. Ramprasad", "N. Bhaskar", "Deepti K."],
    "first name only": ["Meghana", "Siddhesh", "Vaibhavi", "Raghunandan"],
}
N4_CAPS = [name.upper() for name in ["Sailaja Pemmasani", "Nupur Maheshwari", "Abirami Natarajan", "Chinmay Phadke",
                                     "Shabnam Kazmi", "N. Bhaskar", "Meghana", "Pranjal Saikia"]]
N4_LOWERCASE = ["lahari chilukuri", "garima", "jithin", "ipsita sengupta", "harshil thakkar", "srujana"]

N5 = ["Lakshmi Vilas Bank statement", "Kalyan Jewellers - Google Chrome", "Gita Press Books catalogue",
      "Arjun Award winners list", "Sai Baba Temple timings", "Krishna River bridge photos", "Hari Om Traders invoice",
      "Vishnu Sahasranamam audio", "Uday Express timetable", "Aditya Birla Capital login", "Prem Ratan Dhan Payo songs",
      "Ganesh Talkies show times"]
N5_FESTIVALS = ["Ganesh Chaturthi Sale", "Krishna Janmashtami Offers", "Durga Puja Pandal Map"]

N6 = {
    "Telugu": ["Satyanarayana Mutyala", "Hymavathi Kancharla", "Raghuveer Tummala", "Sirisha Atluri",
               "Venkateswarlu Gorrepati", "Jahnavi Movva", "Ravindranath Kotha", "Lavanya Dasari"],
    "Hindi belt": ["Shashank Bajpai", "Ritika Khandelwal", "Dharmendra Chaurasia", "Pragati Dubey",
                   "Yogendra Rathore", "Shalini Bansal", "Mithilesh Kanaujia"],
    "Tamil, Kannada, Malayalam": ["Elango Muthukumaran", "Revathi Chidambaram", "Basavaraj Hiremath",
                                  "Sahana Shanbhag", "Nithin Varghese", "Anjitha Pulikkal", "Thangavel Arumugam"],
    "other regions": ["Arindam Bhattacharjee", "Madhurima Dasgupta", "Sushant Gaikwad", "Hetal Parikh",
                      "Manjot Grewal", "Rukhsar Pathan", "Lalthanpuii Ralte", "Subhashree Pradhan",
                      "Irfan Lone", "Clifford Rodrigues"],
    "initials": ["K.R. Sudhakar", "M. Chandrasekhar", "T. Vasantha", "Gayathri S."],
    "first name only": ["Nagendra", "Pavani", "Ishwari", "Tanmay"],
}
N6_CAPS = [n.upper() for n in ["Hymavathi Kancharla", "Ritika Khandelwal", "Revathi Chidambaram", "Hetal Parikh",
                               "Rukhsar Pathan", "M. Chandrasekhar", "Pavani", "Subhashree Pradhan"]]
N6_LOWERCASE = ["sirisha atluri", "shalini", "nithin", "madhurima dasgupta", "sushant gaikwad", "lavanya"]

O6 = ["Chennai Express - Netflix", "Mumbai Indians vs Chennai Super Kings - Hotstar", "Apollo Pharmacy order status",
      "Infosys Springboard course", "Ganga Aarti live stream", "Taj Mahal tickets - ASI", "Kerala Blasters fixtures",
      "Udupi Grand menu", "Indian Oil fuel bill", "Golden Temple langar timings", "Sundaram Finance EMI",
      "Vande Bharat Express booking - IRCTC", "Haldiram Namkeen offers", "Saravana Bhavan reviews",
      "Shatabdi Express PNR status", "Gateway of India photos", "Meenakshi Temple darshan", "Sabarmati Ashram visit",
      "Hampi travel guide", "Malgudi Days episode 3", "Panchatantra stories PDF", "Kalki trailer - YouTube",
      "Bahubali soundtrack - Spotify", "Lotus Temple visiting hours", "Narmada Bachao Andolan notes",
      "Tirupati Balaji darshan booking", "Brahmaputra river map", "Chandrayaan mission update",
      "Gandhi Jayanti holiday notice", "Ashoka pillar history"]


def names(group_dict: dict) -> list[str]:
    return [name for group in group_dict.values() for name in group]
