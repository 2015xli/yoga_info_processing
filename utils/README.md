5. convert array of courses to use snake case for course names.
json_convert_course_to_use_pose_snakename.py
generate: pattern_course.txt

4. convert category to array of categories
json_convert_category_to_arrays.py  


3. convert the array of poses by normalizing the fields of pose data
json_combine_pose_fields.py         


2. convert the snakecase pose file to array of poses. 
json_convert_pose_to_array.py        


1. convert the pose initial json file to make all the pose names to snakecase.
json_convert_pose_to_snakename.py
generate:
pattern_pose.txt
replacement_pose_keys.log


0. output orginal json file with short values, to control the total file size for AI to process.
json_extract_keys.py
