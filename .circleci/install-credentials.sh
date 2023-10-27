echo "============================================"
echo "$AWS_ACCESS_KEY"
echo $AWS_ACCESS_KEY
echo "$AWS_SECRET_ACCESS_KEY"
echo $AWS_SECRET_ACCESS_KEY
printenv
echo "============================================"
npx sls config credentials \
    --provider aws \
    --profile serverlessUser \
    --key "$AWS_ACCESS_KEY" \
    --secret "$AWS_SECRET_ACCESS_KEY"\