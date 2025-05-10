Extract Yoga pose info from the book "The Modern Yoga Bible (Godsfield Bibles) (Brown, Christina [Brown, Christina]) (Z-Library).pdf. Actually it extracted the .temp.txt file, then did some manual annotations to the text file, and use the text file as input for the final json file generation.

The annotations are mainly two things:
1. to mark the end of a pose section with star. (This is probably unnecessary if my code parses the "Part\s\d\n" and "\d+\s\.\n" as the section endings.)
2. to add a star before the pose name to some poses in the Yoga Mind part, in order to know the beginning of a pose section.


