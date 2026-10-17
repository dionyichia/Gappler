# The object word you said, and when (T2.21). Sent by the aria audio pipeline on
# /aria/audio/prompt_stamped. Times are the glasses' capture clock, the same as the glasses
# image and gaze stamps (T2.19). If the word is not found in the transcript, both times are the
# sentence's start and end.

std_msgs/Header          header     # stamp: when the object word started
string                   word       # object words, or the stop word
builtin_interfaces/Time  word_end   # when the object word ended
